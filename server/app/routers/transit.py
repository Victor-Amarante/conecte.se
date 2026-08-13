"""HTTP access to the transit network.

Used by the React client and, just as importantly, to exercise the spatial
queries without going through WhatsApp.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.services.transit_service import (
    DEFAULT_RADIUS_M,
    TransitService,
    transit_service,
)

router = APIRouter(prefix="/transit", tags=["transit"])

Lat = Query(..., ge=-90, le=90, description="Latitude in WGS84 degrees")
Lon = Query(..., ge=-180, le=180, description="Longitude in WGS84 degrees")


def get_transit_service() -> TransitService:
    return transit_service


@router.get("/stops/nearby")
async def stops_nearby(
    lat: float = Lat,
    lon: float = Lon,
    radius_m: int = Query(DEFAULT_RADIUS_M, ge=50, le=5000),
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
    service: TransitService = Depends(get_transit_service),
) -> dict:
    stops = await service.find_nearby_stops(session, lat, lon, radius_m, limit)
    return {"radius_m": radius_m, "count": len(stops), "stops": [s.as_dict() for s in stops]}


@router.get("/lines/probable")
async def lines_probable(
    lat: float = Lat,
    lon: float = Lon,
    radius_m: int | None = Query(
        None,
        ge=50,
        le=5000,
        description="Fixed radius. Omit to expand automatically until lines are found.",
    ),
    limit: int = Query(8, ge=1, le=25),
    session: AsyncSession = Depends(get_db_session),
    service: TransitService = Depends(get_transit_service),
) -> dict:
    """Lines a user at this point is most likely to be asking about."""
    if radius_m is None:
        lines, used_radius = await service.find_probable_lines_expanding(
            session, lat, lon, limit=limit
        )
    else:
        lines = await service.find_probable_lines(session, lat, lon, radius_m, limit)
        used_radius = radius_m
    return {
        "radius_m": used_radius,
        "count": len(lines),
        "lines": [line.as_dict() for line in lines],
    }


@router.get("/lines/search")
async def lines_search(
    q: str = Query(..., min_length=1, max_length=80),
    limit: int = Query(10, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
    service: TransitService = Depends(get_transit_service),
) -> dict:
    lines = await service.search_lines(session, q, limit)
    return {"count": len(lines), "lines": lines}


@router.get("/lines/{codigo_linha}/itinerary")
async def line_itinerary(
    codigo_linha: str,
    subline_label: str | None = Query(
        "PRI", description="Subline variant; null for the first available"
    ),
    session: AsyncSession = Depends(get_db_session),
    service: TransitService = Depends(get_transit_service),
) -> dict:
    itinerary = await service.get_line_itinerary(session, codigo_linha, subline_label)
    if itinerary is None:
        raise HTTPException(status_code=404, detail=f"line {codigo_linha} not found")
    return itinerary


@router.get("/stops/{stop_id}/lines")
async def stop_lines(
    stop_id: int,
    session: AsyncSession = Depends(get_db_session),
    service: TransitService = Depends(get_transit_service),
) -> dict:
    lines = await service.list_lines_at_stop(session, stop_id)
    return {"stop_id": stop_id, "count": len(lines), "lines": lines}
