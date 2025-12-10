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
            logger.debug(
                f"Calculating ETA: origin=({origin.latitude}, {origin.longitude}), "
                f"destination=({destination.latitude}, {destination.longitude})"
            )
            
            url = f"{self.base_url}/{profile}"
            params = {
                "api_key": self.api_key if self.api_key else "",
                "start": f"{origin.longitude},{origin.latitude}",
                "end": f"{destination.longitude},{destination.latitude}"
            }
            
            if not self.api_key:
                logger.info("No API key provided, using simple ETA calculation")
                return self._calculate_simple_eta(origin, destination)
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                route = data.get("features", [{}])[0].get("properties", {})
                segments = route.get("segments", [{}])
                
                if not segments:
                    logger.warning("No segments in route response, using simple ETA")
                    return self._calculate_simple_eta(origin, destination)
                
                segment = segments[0]
                distance = segment.get("distance", 0) / 1000  # km
                duration = segment.get("duration", 0)  # segundos
                
                if distance == 0 or duration == 0:
                    logger.warning("Invalid route data (distance or duration is 0), using simple ETA")
                    return self._calculate_simple_eta(origin, destination)
                
                result = {
                    "distance_km": round(distance, 2),
                    "duration_minutes": int(round(duration / 60)),
                    "duration_seconds": int(duration)
                }
                
                logger.info(f"ETA calculated successfully: {result}")
                return result
            else:
                logger.warning(
                    f"ETA API error: {response.status_code} - {response.text[:200]}"
                )
                return self._calculate_simple_eta(origin, destination)
                
        except requests.exceptions.Timeout:
            logger.error("ETA API request timeout, using simple ETA")
            return self._calculate_simple_eta(origin, destination)
        except requests.exceptions.RequestException as e:
            logger.error(f"ETA API request error: {e}, using simple ETA")
            return self._calculate_simple_eta(origin, destination)
        except Exception as e:
            logger.error(f"Unexpected error calculating ETA: {e}", exc_info=True)
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
        
        R = 6371  # Raio da Terra em km
        distance_km = R * c
        
        avg_speed_kmh = 30
        duration_hours = distance_km / avg_speed_kmh
        duration_minutes = duration_hours * 60
        
        result = {
            "distance_km": round(distance_km, 2),
            "duration_minutes": int(round(duration_minutes)),
            "duration_seconds": int(duration_minutes * 60),
            "note": "Estimativa aproximada"
        }
        
        logger.info(f"Simple ETA calculated: {result}")
        return result
