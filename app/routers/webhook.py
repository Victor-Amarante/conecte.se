from loguru import logger
from fastapi import APIRouter, Request, Depends
from app.services.evolution_service import EvolutionApiService
from app.dependencies import get_evolution_service
from app.utils.extract_user_number import extract_user_number

router = APIRouter()

@router.post("/webhook")
async def evolution_webhook(request: Request, evolution_service: EvolutionApiService = Depends(get_evolution_service)):
    body = await request.json()
    logger.info(f"Webhook received: {body}")

    try:
        key = body["data"]["key"]
    except Exception:
        return {"status": "ignored", "reason": "invalid payload (missing key)"}

    user_number = extract_user_number(key)
    if not user_number:
        return {"status": "ignored", "reason": "masked user (LID) - cannot respond"}
    
    remote_jid = key.get("remoteJid", "")
    if "@g.us" in remote_jid:
        return {"status": "ignored", "reason": "message from group"}

    from_me = key.get("fromMe", False)
    if from_me:
        return {"status": "ignored", "reason": "message from bot"}
    
    message_data = body["data"].get("message", {})
    message = (
        message_data.get("conversation")
        or message_data.get("extendedTextMessage", {}).get("text")
    )

    if not message:
        return {"status": "ignored", "reason": "empty or unsupported message type"}
    
    reply_text = f"Recebi sua mensagem: {message}"
    
    try:
        evolution_service.send_text_message(user_number, reply_text)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    return {
        "status": "ok",
        "user": user_number,
        "message_received": message,
        "reply_sent": reply_text
    }
