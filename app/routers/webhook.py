from loguru import logger
from fastapi import APIRouter, Request, Depends
from app.services.evolution_service import EvolutionApiService
from app.dependencies import get_evolution_service

router = APIRouter()

@router.post("/webhook")
async def evolution_webhook(request: Request, evolution_service: EvolutionApiService = Depends(get_evolution_service)):
    body = await request.json()
    logger.info(f"Webhook received: {body}")

    try:
        remote_jid = body["data"]["key"]["remoteJid"]
        from_me = body["data"]["key"]["fromMe"]
        message = (
            body["data"]["message"].get("conversation")
            or body["data"]["message"].get("extendedTextMessage", {}).get("text")
        )
    except Exception:
        return {"status": "ignored", "reason": "payload format not recognized"}

    if from_me:
        return {"status": "ignored", "reason": "message from bot"}
    
    if "@g.us" in remote_jid:
        return {"status": "ignored", "reason": "message from group"}
    
    user_number = remote_jid.replace("@s.whatsapp.net", "")
    reply_text = f"Recebi sua mensagem: {message}"

    try:
        evolution_service.send_text_message(user_number, reply_text)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    return {"status": "ok",
            "user": user_number,
            "message_received": message,
            "reply_sent": reply_text}
