from fastapi import APIRouter, Depends

from app.dependencies import get_bus_location_service
from app.schemas.location import BusLocation
from app.schemas.webhook import LocationReceivedResponse
from app.services.bus_location_service import BusLocationService

router = APIRouter()


@router.post("/location", response_model=LocationReceivedResponse)
async def receive_location(
    bus_location: BusLocation,
    bus_location_service: BusLocationService = Depends(get_bus_location_service),
) -> LocationReceivedResponse:
    bus_location_service.update_location(bus_location)
    return LocationReceivedResponse(data=bus_location.model_dump())
