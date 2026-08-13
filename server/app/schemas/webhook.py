from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel

MessageKind = Literal["text", "location"]


@dataclass(frozen=True)
class ParsedMessage:
    """A webhook payload reduced to what the assistant needs.

    ``kind`` discriminates the two message types we act on: plain text, and a
    pinned location sent through the WhatsApp attachment menu.
    """

    user_number: str
    kind: MessageKind
    text: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    @property
    def is_location(self) -> bool:
        return self.kind == "location"


class WebhookResponse(BaseModel):
    status: str
    user: str
    message_received: str
    reply_sent: str
    eta_available: bool
    kind: MessageKind = "text"
    tools_used: list[str] = []


class WebhookIgnoredResponse(BaseModel):
    status: str = "ignored"
    reason: str


class LocationReceivedResponse(BaseModel):
    status: str = "ok"
    message: str = "Bus location received successfully"
    data: dict


class ErrorResponse(BaseModel):
    status: str = "error"
    detail: str
