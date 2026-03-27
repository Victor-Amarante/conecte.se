from math import radians, cos, sin, asin, sqrt
from typing import Optional

import httpx
from loguru import logger

from app.schemas.location import BusLocation, UserLocation


class ETAService:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self.base_url = "https://api.openrouteservice.org/v2/directions"
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    async def calculate_eta(
        self,
        origin: BusLocation,
        destination: UserLocation,
        profile: str = "driving-car",
    ) -> Optional[dict]:
        logger.debug(
            f"Calculating ETA: origin=({origin.latitude}, {origin.longitude}), "
            f"destination=({destination.latitude}, {destination.longitude})"
        )

        if not self.api_key:
            logger.info("No API key provided, using simple ETA calculation")
            return self._calculate_simple_eta(origin, destination)

        url = f"{self.base_url}/{profile}"
        params = {
            "api_key": self.api_key,
            "start": f"{origin.longitude},{origin.latitude}",
            "end": f"{destination.longitude},{destination.latitude}",
        }

        try:
            client = await self._get_client()
            response = await client.get(url, params=params)
        except httpx.TimeoutException:
            logger.error("ETA API request timeout, using simple ETA")
            return self._calculate_simple_eta(origin, destination)
        except httpx.RequestError as e:
            logger.error(f"ETA API request error: {e}, using simple ETA")
            return self._calculate_simple_eta(origin, destination)

        if response.status_code != 200:
            logger.warning(
                f"ETA API error: {response.status_code} - {response.text[:200]}"
            )
            return self._calculate_simple_eta(origin, destination)

        data = response.json()
        route = data.get("features", [{}])[0].get("properties", {})
        segments = route.get("segments", [{}])

        if not segments:
            logger.warning("No segments in route response, using simple ETA")
            return self._calculate_simple_eta(origin, destination)

        segment = segments[0]
        distance = segment.get("distance", 0) / 1000
        duration = segment.get("duration", 0)

        if distance == 0 or duration == 0:
            logger.warning("Invalid route data (distance or duration is 0), using simple ETA")
            return self._calculate_simple_eta(origin, destination)

        result = {
            "distance_km": round(distance, 2),
            "duration_minutes": int(round(duration / 60)),
            "duration_seconds": int(duration),
        }

        logger.info(f"ETA calculated successfully: {result}")
        return result

    def _calculate_simple_eta(self, origin: BusLocation, destination: UserLocation) -> dict:
        """Haversine-based straight-line estimate (no real routing)."""
        lat1, lon1 = radians(origin.latitude), radians(origin.longitude)
        lat2, lon2 = radians(destination.latitude), radians(destination.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        earth_radius_km = 6371
        distance_km = earth_radius_km * c

        avg_speed_kmh = 30
        duration_minutes = (distance_km / avg_speed_kmh) * 60

        result = {
            "distance_km": round(distance_km, 2),
            "duration_minutes": int(round(duration_minutes)),
            "duration_seconds": int(duration_minutes * 60),
            "note": "Estimativa aproximada",
        }

        logger.info(f"Simple ETA calculated: {result}")
        return result

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
