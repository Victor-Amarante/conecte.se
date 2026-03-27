from pydantic import BaseModel
from typing import Optional


class WebhookResponse(BaseModel):
    status: str
    user: str
    message_received: str
    reply_sent: str
    eta_available: bool


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
