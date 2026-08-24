"""Payload handling for the Evolution webhook.

The location cases matter most: before this change a pinned location was
discarded as an unsupported message type, which is exactly the input the whole
line-selection flow depends on.
"""

import pytest

from app.core.exceptions import WebhookIgnoredError, WebhookPayloadError
from app.services.webhook_service import WebhookService


@pytest.fixture
def service():
    return WebhookService(evolution_service=None, agent_factory=None)


def payload(message: dict, **key_overrides) -> dict:
    key = {"remoteJid": "5581999999999@s.whatsapp.net", "fromMe": False}
    key.update(key_overrides)
    return {"event": "messages.upsert", "data": {"key": key, "message": message}}


class TestNonMessageEvents:
    """A Evolution entrega todos os eventos no mesmo webhook.

    Responder 400 a um `qrcode.updated` faz a Evolution marcar falha e
    reagendar a entrega em loop, enchendo o log de erro durante o pareamento.
    """

    @pytest.mark.parametrize(
        "event",
        ["qrcode.updated", "connection.update", "contacts.upsert", "chats.update"],
    )
    def test_non_message_events_are_ignored_not_rejected(self, service, event):
        with pytest.raises(WebhookIgnoredError, match="not handled"):
            service._parse_payload({"event": event, "data": {"qrcode": "..."}})

    def test_messages_upsert_is_processed(self, service):
        parsed = service._parse_payload(payload({"conversation": "oi"}))
        assert parsed.kind == "text"

    def test_underscore_spelling_is_accepted(self, service):
        body = payload({"conversation": "oi"})
        body["event"] = "messages_upsert"
        assert service._parse_payload(body).text == "oi"

    def test_payload_without_an_event_field_still_works(self, service):
        """Nem toda configuração da Evolution manda o campo `event`."""
        body = payload({"conversation": "oi"})
        del body["event"]
        assert service._parse_payload(body).text == "oi"


class TestTextMessages:
    def test_plain_conversation(self, service):
        parsed = service._parse_payload(payload({"conversation": "onde está o 011?"}))

        assert parsed.user_number == "5581999999999"
        assert parsed.kind == "text"
        assert parsed.text == "onde está o 011?"
        assert parsed.latitude is None

    def test_extended_text(self, service):
        parsed = service._parse_payload(
            payload({"extendedTextMessage": {"text": "e o próximo?"}})
        )

        assert parsed.kind == "text"
        assert parsed.text == "e o próximo?"


class TestLocationMessages:
    def test_pinned_location_is_parsed(self, service):
        parsed = service._parse_payload(
            payload(
                {
                    "locationMessage": {
                        "degreesLatitude": -8.04887728646683,
                        "degreesLongitude": -34.95138771773008,
                    }
                }
            )
        )

        assert parsed.kind == "location"
        assert parsed.is_location
        assert parsed.latitude == pytest.approx(-8.048877)
        assert parsed.longitude == pytest.approx(-34.951388)
        assert parsed.text  # the agent still needs something to react to

    def test_live_location_is_parsed(self, service):
        parsed = service._parse_payload(
            payload(
                {
                    "liveLocationMessage": {
                        "degreesLatitude": -8.05,
                        "degreesLongitude": -34.9,
                    }
                }
            )
        )

        assert parsed.kind == "location"
        assert parsed.latitude == pytest.approx(-8.05)

    def test_null_island_is_rejected(self, service):
        """WhatsApp sends (0, 0) when it cannot resolve a location."""
        with pytest.raises(WebhookIgnoredError):
            service._parse_payload(
                payload(
                    {"locationMessage": {"degreesLatitude": 0, "degreesLongitude": 0}}
                )
            )

    def test_incomplete_location_falls_through(self, service):
        with pytest.raises(WebhookIgnoredError):
            service._parse_payload(
                payload({"locationMessage": {"degreesLatitude": -8.05}})
            )

    def test_location_wins_over_a_caption(self, service):
        parsed = service._parse_payload(
            payload(
                {
                    "conversation": "aqui",
                    "locationMessage": {
                        "degreesLatitude": -8.05,
                        "degreesLongitude": -34.9,
                    },
                }
            )
        )

        assert parsed.kind == "location"


class TestIgnoredAndInvalid:
    def test_group_messages_are_ignored(self, service):
        with pytest.raises(WebhookIgnoredError, match="group"):
            service._parse_payload(
                payload({"conversation": "oi"}, remoteJid="12345@g.us")
            )

    def test_own_messages_are_ignored(self, service):
        with pytest.raises(WebhookIgnoredError, match="bot"):
            service._parse_payload(payload({"conversation": "oi"}, fromMe=True))

    def test_lid_masked_users_are_ignored(self, service):
        with pytest.raises(WebhookIgnoredError, match="LID"):
            service._parse_payload(
                payload({"conversation": "oi"}, remoteJid="12345@lid")
            )

    def test_lid_with_a_resolved_number_is_processed(self, service):
        """O WhatsApp manda o LID no remoteJid e o telefone no `senderPn`.

        Na primeira mensagem de um contato novo o `senderPn` costuma vir vazio,
        e a mensagem é descartada — foi por isso que os primeiros testes
        precisaram ser enviados duas vezes.
        """
        parsed = service._parse_payload(
            payload(
                {"conversation": "oi"},
                remoteJid="148271481798877@lid",
                senderPn="558198188404@s.whatsapp.net",
            )
        )

        assert parsed.user_number == "558198188404"

    def test_empty_message_is_ignored(self, service):
        with pytest.raises(WebhookIgnoredError, match="empty"):
            service._parse_payload(payload({}))

    def test_unsupported_type_is_ignored(self, service):
        with pytest.raises(WebhookIgnoredError, match="empty"):
            service._parse_payload(payload({"audioMessage": {"url": "..."}}))

    def test_null_message_object_is_ignored(self, service):
        with pytest.raises(WebhookIgnoredError):
            service._parse_payload({"data": {"key": {"remoteJid": "1@s.whatsapp.net"}, "message": None}})

    def test_missing_key_is_a_payload_error(self, service):
        with pytest.raises(WebhookPayloadError):
            service._parse_payload({"data": {}})

    def test_missing_data_is_a_payload_error(self, service):
        with pytest.raises(WebhookPayloadError):
            service._parse_payload({})
