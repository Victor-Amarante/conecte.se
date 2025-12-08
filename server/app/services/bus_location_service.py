# server/app/services/bus_location_service.py
from typing import Optional
from app.schemas.location import BusLocation

class BusLocationService:
    def __init__(self):
        self._current_location: Optional[BusLocation] = None
    
    def update_location(self, location: BusLocation):
        """Atualiza a localização atual do ônibus"""
        self._current_location = location
    
    def get_current_location(self) -> Optional[BusLocation]:
        """Retorna a localização atual do ônibus"""
        return self._current_location
    
    def has_location(self) -> bool:
        """Verifica se há localização disponível"""
        return self._current_location is not None