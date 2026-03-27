from fastapi import APIRouter, Depends, Request

from app.dependencies import get_webhook_service
from app.schemas.webhook import WebhookResponse
from app.services.webhook_service import WebhookService

router = APIRouter()


@router.post("/webhook", response_model=WebhookResponse)
async def evolution_webhook(
    request: Request,
    webhook_service: WebhookService = Depends(get_webhook_service),
) -> WebhookResponse:
    body = await request.json()
    return await webhook_service.handle(body)
