from pydantic import BaseModel
from typing import Optional

class BusLocation(BaseModel):
  latitude: float
  longitude: float
  accuracy: Optional[float] = None
  timestamp: Optional[int] = None
  
class UserLocation(BaseModel):
  latitude: float
  longitude: float