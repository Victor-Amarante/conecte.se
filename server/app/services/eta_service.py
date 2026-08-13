"""ETA between a bus and a boarding point, via the Google Routes API.

Routes API (``directions/v2:computeRoutes``) is used instead of the legacy
Directions API because ``TRAFFIC_AWARE`` routing is what makes the estimate
worth showing at all in Recife traffic.

Every failure path — no key, timeout, transport error, non-200, unparseable
body — degrades to the Haversine estimate rather than returning nothing, so the
assistant always has something to say.
"""

import time
from math import asin, cos, radians, sin, sqrt
from typing import Optional

import httpx
from loguru import logger

from app.schemas.location import BusLocation, UserLocation

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"
FIELD_MASK = "routes.duration,routes.distanceMeters"

# Routes API is billed per request; a bus barely moves within this window.
CACHE_TTL_SECONDS = 30
AVG_SPEED_KMH = 30


class ETAService:
    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[tuple, tuple[float, dict]] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=10.0)
        return self._client

    @staticmethod
    def _cache_key(origin: BusLocation, destination: UserLocation) -> tuple:
        # ~11 m of precision: finer than that and the cache never hits.
        return (
            round(origin.latitude, 4),
            round(origin.longitude, 4),
            round(destination.latitude, 4),
            round(destination.longitude, 4),
        )

    async def calculate_eta(
        self,
        origin: BusLocation,
        destination: UserLocation,
        profile: str = "DRIVE",
    ) -> Optional[dict]:
        logger.debug(
            f"Calculating ETA: origin=({origin.latitude}, {origin.longitude}), "
            f"destination=({destination.latitude}, {destination.longitude})"
        )

        if not self.api_key:
            logger.info("No Google Maps API key, using simple ETA calculation")
            return self._calculate_simple_eta(origin, destination)

        key = self._cache_key(origin, destination)
        cached = self._cache.get(key)
        if cached and (time.monotonic() - cached[0]) < CACHE_TTL_SECONDS:
            logger.debug("ETA cache hit")
            return cached[1]

        payload = {
            "origin": {
                "location": {
                    "latLng": {
                        "latitude": origin.latitude,
                        "longitude": origin.longitude,
                    }
                }
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destination.latitude,
                        "longitude": destination.longitude,
                    }
                }
            },
            "travelMode": profile,
            "routingPreference": "TRAFFIC_AWARE",
            "languageCode": "pt-BR",
            "units": "METRIC",
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        try:
            client = await self._get_client()
            response = await client.post(ROUTES_URL, json=payload, headers=headers)
        except httpx.TimeoutException:
            logger.error("Routes API timeout, using simple ETA")
            return self._calculate_simple_eta(origin, destination)
        except httpx.RequestError as e:
            logger.error(f"Routes API request error: {e}, using simple ETA")
            return self._calculate_simple_eta(origin, destination)

        if response.status_code != 200:
            logger.warning(
                f"Routes API error: {response.status_code} - {response.text[:200]}"
            )
            return self._calculate_simple_eta(origin, destination)

        result = self._parse_routes_response(response.json())
        if result is None:
            return self._calculate_simple_eta(origin, destination)

        self._cache[key] = (time.monotonic(), result)
        logger.info(f"ETA calculated successfully: {result}")
        return result

    @staticmethod
    def _parse_routes_response(data: dict) -> Optional[dict]:
        routes = data.get("routes") or []
        if not routes:
            logger.warning("No routes in Routes API response")
            return None

        route = routes[0]
        distance_m = route.get("distanceMeters")
        # Routes API returns duration as a protobuf string like "1234s".
        raw_duration = route.get("duration")
        if distance_m is None or not raw_duration:
            logger.warning(f"Incomplete route in response: {route}")
            return None

        try:
            duration_seconds = float(str(raw_duration).rstrip("s"))
        except ValueError:
            logger.warning(f"Unparseable duration: {raw_duration!r}")
            return None

        if distance_m == 0 or duration_seconds == 0:
            logger.warning("Route has zero distance or duration")
            return None

        return {
            "distance_km": round(distance_m / 1000, 2),
            "duration_minutes": max(1, int(round(duration_seconds / 60))),
            "duration_seconds": int(duration_seconds),
        }

    def _calculate_simple_eta(
        self, origin: BusLocation, destination: UserLocation
    ) -> dict:
        """Haversine-based straight-line estimate (no real routing)."""
        lat1, lon1 = radians(origin.latitude), radians(origin.longitude)
        lat2, lon2 = radians(destination.latitude), radians(destination.longitude)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))

        earth_radius_km = 6371
        distance_km = earth_radius_km * c

        duration_minutes = (distance_km / AVG_SPEED_KMH) * 60

        result = {
            "distance_km": round(distance_km, 2),
            "duration_minutes": max(1, int(round(duration_minutes))),
            "duration_seconds": int(duration_minutes * 60),
            "note": "Estimativa aproximada",
        }

        logger.info(f"Simple ETA calculated: {result}")
        return result

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
