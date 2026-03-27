from typing import Optional

from loguru import logger

from app.core.config import settings
from app.core.exceptions import WebhookPayloadError, WebhookIgnoredError
from app.schemas.location import UserLocation
from app.schemas.webhook import WebhookResponse
from app.services.ai_service import AIService
from app.services.bus_location_service import BusLocationService
from app.services.eta_service import ETAService
from app.services.evolution_service import EvolutionApiService
from app.utils.extract_user_number import extract_user_number


class WebhookService:
    def __init__(
        self,
        evolution_service: EvolutionApiService,
        ai_service: AIService,
        bus_location_service: BusLocationService,
        eta_service: ETAService,
    ) -> None:
        self._evolution = evolution_service
        self._ai = ai_service
        self._bus_location = bus_location_service
        self._eta = eta_service

    async def handle(self, body: dict) -> WebhookResponse:
        user_number, message = self._parse_payload(body)
        logger.info(f"Processing message from {user_number}: {message}")

        eta_data = await self._get_eta_data()

        ai_response = await self._ai.generate_response(
            user_message=message,
            eta_data=eta_data,
        )
        logger.info(f"AI response generated: {ai_response}")

        await self._evolution.send_text_message(user_number, ai_response)
        logger.info(f"Message sent successfully to {user_number}")

        return WebhookResponse(
            status="ok",
            user=user_number,
            message_received=message,
            reply_sent=ai_response,
            eta_available=eta_data is not None,
        )

    def _parse_payload(self, body: dict) -> tuple[str, str]:
        """Validate the webhook body and extract (user_number, message_text).

        Raises WebhookPayloadError or WebhookIgnoredError when the message
        should not be processed.
        """
        try:
            key = body["data"]["key"]
        except (KeyError, TypeError) as e:
            raise WebhookPayloadError("invalid payload (missing key)") from e

        user_number = extract_user_number(key)
        if not user_number:
            raise WebhookIgnoredError("masked user (LID) - cannot respond")

        remote_jid = key.get("remoteJid", "")
        if "@g.us" in remote_jid:
            raise WebhookIgnoredError("message from group")

        if key.get("fromMe", False):
            raise WebhookIgnoredError("message from bot")

        message_data = body["data"].get("message", {})
        message = (
            message_data.get("conversation")
            or message_data.get("extendedTextMessage", {}).get("text")
        )

        if not message:
            raise WebhookIgnoredError("empty or unsupported message type")

        return user_number, message

    async def _get_eta_data(self) -> Optional[dict]:
        bus_location = self._bus_location.get_current_location()

        if not bus_location:
            logger.info("Skipping ETA calculation - no bus location")
            return None

        logger.info(
            f"Bus location available: lat={bus_location.latitude}, "
            f"lon={bus_location.longitude}"
        )

        user_location = UserLocation(
            latitude=settings.user_latitude,
            longitude=settings.user_longitude,
        )

        try:
            eta_data = await self._eta.calculate_eta(
                origin=bus_location,
                destination=user_location,
                profile="driving-car",
            )
            if eta_data:
                logger.info(
                    f"ETA calculated: {eta_data.get('distance_km')} km, "
                    f"{eta_data.get('duration_minutes')} min"
                )
            else:
                logger.warning("ETA calculation returned None")
            return eta_data
        except Exception as e:
            logger.error(f"Error calculating ETA: {e}", exc_info=True)
            return None
