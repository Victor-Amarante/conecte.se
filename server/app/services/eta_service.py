import requests
from typing import Optional, Tuple
from app.schemas.location import BusLocation, UserLocation
from loguru import logger

class ETAService:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.openrouteservice.org/v2/directions"
    
    def calculate_eta(
        self, 
        origin: BusLocation, 
        destination: UserLocation,
        profile: str = "driving-car"
    ) -> Optional[dict]:
        try:
            url = f"{self.base_url}/{profile}"
            params = {
                "api_key": self.api_key if self.api_key else "",
                "start": f"{origin.longitude},{origin.latitude}",
                "end": f"{destination.longitude},{destination.latitude}"
            }
            
            if not self.api_key:
                return self._calculate_simple_eta(origin, destination)
            
            response = requests.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                route = data.get("features", [{}])[0].get("properties", {})
                distance = route.get("segments", [{}])[0].get("distance", 0) / 1000  # km
                duration = route.get("segments", [{}])[0].get("duration", 0)  # segundos
                
                return {
                    "distance_km": round(distance, 2),
                    "duration_minutes": round(duration / 60, 1),
                    "duration_seconds": int(duration)
                }
            else:
                logger.warning(f"ETA API error: {response.status_code}")
                return self._calculate_simple_eta(origin, destination)
                
        except Exception as e:
            logger.error(f"Error calculating ETA: {e}")
            return self._calculate_simple_eta(origin, destination)
    
    def _calculate_simple_eta(self, origin: BusLocation, destination: UserLocation) -> dict:
        """
        Calcula distância e estimativa de tempo usando fórmula de Haversine
        (estimativa simples, não considera rotas reais)
        """
        from math import radians, cos, sin, asin, sqrt
        
        lat1, lon1 = radians(origin.latitude), radians(origin.longitude)
        lat2, lon2 = radians(destination.latitude), radians(destination.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * asin(sqrt(a))
        
        R = 6371
        distance_km = R * c
        
        avg_speed_kmh = 30
        duration_hours = distance_km / avg_speed_kmh
        duration_minutes = duration_hours * 60
        
        return {
            "distance_km": round(distance_km, 2),
            "duration_minutes": round(duration_minutes, 1),
            "duration_seconds": int(duration_minutes * 60),
            "note": "Estimativa aproximada"
        }
