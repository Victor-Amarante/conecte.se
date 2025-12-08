from typing import Optional
from app.schemas.location import BusLocation

class BusLocationService:
    def __init__(self):
        self._current_location: Optional[BusLocation] = None
    
    def update_location(self, location: BusLocation):
        self._current_location = location
    
    def get_current_location(self) -> Optional[BusLocation]:
        return self._current_location
    
    def has_location(self) -> bool:
        return self._current_location is not None