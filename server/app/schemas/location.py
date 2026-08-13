from typing import Optional

from pydantic import BaseModel, Field


class BusLocation(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    accuracy: Optional[float] = None
    timestamp: Optional[int] = None
    # Which line this vehicle is running. Optional so the existing single-bus
    # tracker keeps working without changes.
    codigo_linha: Optional[str] = None


class UserLocation(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
