from loguru import logger

from app.agent.graph import ConecteseAgent
from app.core.exceptions import WebhookIgnoredError, WebhookPayloadError
from app.db.models import MessageLog
from app.db.session import SessionLocal
from app.schemas.webhook import ParsedMessage, WebhookResponse
from app.services.evolution_service import EvolutionApiService
from app.services.session_service import session_service
from app.utils.extract_user_number import extract_user_number

LOCATION_ACK = "Localização recebida 📍"

# Único evento da Evolution que representa uma mensagem recebida. Aceitamos as
# duas grafias porque a Evolution usa ponto no corpo do webhook e underscore em
# alguns modos de configuração.
MESSAGE_EVENTS = {"messages.upsert", "messages_upsert"}


class WebhookService:
    def __init__(
        self,
        evolution_service: EvolutionApiService,
        agent_factory,
    ) -> None:
        self._evolution = evolution_service
        # A factory rather than an instance: the agent needs an async build
        # (checkpointer setup, MCP tools) that cannot run at import time.
        self._agent_factory = agent_factory

    async def handle(self, body: dict) -> WebhookResponse:
        parsed = self._parse_payload(body)
        logger.info(
            f"Processing {parsed.kind} message from {parsed.user_number}: {parsed.text}"
        )

        async with SessionLocal() as session:
            if parsed.is_location:
                await session_service.save_location(
                    session, parsed.user_number, parsed.latitude, parsed.longitude
                )
            user_session = await session_service.get(session, parsed.user_number)

        latitude = longitude = None
        if session_service.has_fresh_location(user_session):
            latitude = user_session.last_latitude
            longitude = user_session.last_longitude

        agent: ConecteseAgent = await self._agent_factory()
        reply, tools_used = await agent.respond(
            whatsapp_number=parsed.user_number,
            user_message=parsed.text,
            latitude=latitude,
            longitude=longitude,
            location_age_seconds=session_service.location_age_seconds(user_session),
            selected_line=user_session.selected_codigo_linha if user_session else None,
        )
        logger.info(f"Agent replied (tools={tools_used}): {reply}")

        await self._evolution.send_text_message(parsed.user_number, reply)
        logger.info(f"Message sent successfully to {parsed.user_number}")

        await self._log_message(parsed, reply, tools_used)

        return WebhookResponse(
            status="ok",
            user=parsed.user_number,
            message_received=parsed.text,
            reply_sent=reply,
            eta_available="get_bus_eta" in tools_used,
            kind=parsed.kind,
            tools_used=tools_used,
        )

    async def _log_message(
        self, parsed: ParsedMessage, reply: str, tools_used: list[str]
    ) -> None:
        """Auditing must never break a reply the user already received."""
        try:
            async with SessionLocal() as session:
                session.add(
                    MessageLog(
                        user_number=parsed.user_number,
                        user_message=parsed.text,
                        ai_response=reply,
                        tools_used=tools_used,
                    )
                )
                await session.commit()
        except Exception as exc:
            logger.warning(f"Could not persist message log: {exc}")

    def _parse_payload(self, body: dict) -> ParsedMessage:
        """Validate the webhook body and reduce it to a ParsedMessage.

        Raises WebhookPayloadError or WebhookIgnoredError when the message
        should not be processed.
        """
        # A Evolution entrega TODOS os eventos no mesmo webhook quando
        # WEBHOOK_GLOBAL_WEBHOOK_BY_EVENTS=false: qrcode.updated,
        # connection.update, contacts.upsert e outros. Responder 400 a eles
        # faz a Evolution registrar erro e reagendar entrega em loop, então
        # tudo que não for mensagem é ignorado com 200.
        event = body.get("event")
        if event and event not in MESSAGE_EVENTS:
            raise WebhookIgnoredError(f"event not handled: {event}")

        try:
            key = body["data"]["key"]
        except (KeyError, TypeError) as e:
            raise WebhookPayloadError("invalid payload (missing key)") from e

        # Order matters: a group JID has no extractable user number, so
        # checking it first keeps the ignore reason honest in the logs.
        remote_jid = key.get("remoteJid", "")
        if "@g.us" in remote_jid:
            raise WebhookIgnoredError("message from group")

        if key.get("fromMe", False):
            raise WebhookIgnoredError("message from bot")

        user_number = extract_user_number(key)
        if not user_number:
            raise WebhookIgnoredError("masked user (LID) - cannot respond")

        message_data = body["data"].get("message") or {}

        location = self._extract_location(message_data)
        if location is not None:
            latitude, longitude = location
            return ParsedMessage(
                user_number=user_number,
                kind="location",
                # The agent sees the location as context, not as free text; a
                # short marker keeps the transcript readable.
                text=LOCATION_ACK,
                latitude=latitude,
                longitude=longitude,
            )

        text = message_data.get("conversation") or message_data.get(
            "extendedTextMessage", {}
        ).get("text")

        if not text:
            raise WebhookIgnoredError("empty or unsupported message type")

        return ParsedMessage(user_number=user_number, kind="text", text=text)

    @staticmethod
    def _extract_location(message_data: dict) -> tuple[float, float] | None:
        """Pull coordinates out of a WhatsApp location message.

        Evolution forwards both the one-off ``locationMessage`` and the
        ``liveLocationMessage`` used by live sharing; both carry the same
        ``degreesLatitude``/``degreesLongitude`` fields.
        """
        for field in ("locationMessage", "liveLocationMessage"):
            payload = message_data.get(field)
            if not isinstance(payload, dict):
                continue
            latitude = payload.get("degreesLatitude")
            longitude = payload.get("degreesLongitude")
            if latitude is None or longitude is None:
                continue
            try:
                latitude, longitude = float(latitude), float(longitude)
            except (TypeError, ValueError):
                continue
            # WhatsApp sends (0, 0) for a location it failed to resolve.
            if latitude == 0 and longitude == 0:
                continue
            return latitude, longitude
        return None
