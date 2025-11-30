from fastapi import APIRouter, Request, Depends
from app.services.evolution_service import EvolutionApiService
from app.dependencies import get_evolution_service

router = APIRouter()

@router.post("/webhook")
async def evolution_webhook(request: Request, evolution_service: EvolutionApiService = Depends(get_evolution_service)):
    body = await request.json()

    try:
        remote_jid = body["data"]["key"]["remoteJid"]
        message = (
            body["data"]["message"].get("conversation")
            or body["data"]["message"].get("extendedTextMessage", {}).get("text")
        )
    except:
        return {"status": "ignored", "reason": "payload format not recognized"}


    user_number = remote_jid.replace("@s.whatsapp.net", "")

   
    if "@g.us" in remote_jid:
        return {"status": "ignored", "reason": "group message"}


    reply_text = f"Recebi sua mensagem: {message}"

    try:
        evolution_service.send_text_message(user_number, reply_text)
    except Exception as e:
        return {"status": "error", "detail": str(e)}

    return {"status": "ok", "user": user_number, "message": message}
