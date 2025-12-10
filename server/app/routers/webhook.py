from loguru import logger
from typing import Optional
from fastapi import APIRouter, Request, Depends
from app.services.evolution_service import EvolutionApiService
from app.services.ai_service import AIService
from app.services.bus_location_service import BusLocationService
from app.services.eta_service import ETAService
from app.schemas.location import UserLocation, BusLocation
from app.dependencies import get_evolution_service, get_ai_service, get_bus_location_service, get_eta_service
from app.utils.extract_user_number import extract_user_number
from app.core.config import settings

router = APIRouter()

@router.post("/webhook")
async def evolution_webhook(
    request: Request,
    evolution_service: EvolutionApiService = Depends(get_evolution_service),
    ai_service: AIService = Depends(get_ai_service),
    bus_location_service: BusLocationService = Depends(get_bus_location_service),
    eta_service: ETAService = Depends(get_eta_service),
):
    body = await request.json()
    logger.debug(f"Webhook received: {body}")

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
    
    logger.info(f"Processing message from {user_number}: {message}")
    
    user_location = UserLocation(
        latitude=float(settings.user_latitude),
        longitude=float(settings.user_longitude),
    )
    
    bus_location = bus_location_service.get_current_location()
    
    if not bus_location:
        logger.warning("No valid bus location available for ETA calculation")
    else:
        logger.info(
            f"Bus location available: lat={bus_location.latitude}, "
            f"lon={bus_location.longitude}"
        )
    
    eta_data: Optional[dict] = None
    if bus_location:
        try:
            eta_data = eta_service.calculate_eta(
                origin=bus_location,
                destination=user_location,
                profile="driving-car"
            )
            if eta_data:
                logger.info(
                    f"ETA calculated: {eta_data.get('distance_km')} km, "
                    f"{eta_data.get('duration_minutes')} min"
                )
            else:
                logger.warning("ETA calculation returned None")
        except Exception as e:
            logger.error(f"Error calculating ETA: {e}", exc_info=True)
            eta_data = None
    else:
        logger.info("Skipping ETA calculation - no bus location")
    
    ai_response = await ai_service.generate_response(
        user_message=message,
        eta_data=eta_data,
    )
    
    logger.info(f"AI response generated: {ai_response}")
    
    try:
        evolution_service.send_text_message(user_number, ai_response)
        logger.info(f"Message sent successfully to {user_number}")
    except Exception as e:
        logger.error(f"Error sending message: {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}

    return {
        "status": "ok",
        "user": user_number,
        "message_received": message,
        "reply_sent": ai_response,
        "eta_available": eta_data is not None
    }
