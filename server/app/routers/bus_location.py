from fastapi import APIRouter, Depends, HTTPException
from app.schemas.location import BusLocation
from app.services.bus_location_service import BusLocationService
from app.dependencies import get_bus_location_service
from loguru import logger

router = APIRouter()

@router.post("/location")
async def receive_location(
    bus_location: BusLocation,
    bus_location_service: BusLocationService = Depends(get_bus_location_service),
):
    """Recebe localização do ônibus do frontend e armazena"""
    try:
      bus_location_service.update_location(bus_location)
      logger.info(f"Bus location received from frontend: {bus_location.latitude}, {bus_location.longitude}")
      return {
          "status": "ok",
          "message": "Bus location received successfully",
          "data": bus_location.model_dump()
      }
    except Exception as e:
      logger.error(f"Error receiving bus location: {e}")
      raise HTTPException(status_code=500, detail=str(e))
