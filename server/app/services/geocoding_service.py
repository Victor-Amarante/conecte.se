"""Converte um destino escrito à mão em coordenadas.

O passageiro digita "Shopping Recife", "TI Barro" ou "Rua da Aurora, 200" — não
uma latitude. A Geocoding API do Google resolve isso, e é enviesada para
Pernambuco para que "Boa Viagem" caia no Recife e não em outro estado.
"""

from dataclasses import dataclass

import httpx
from loguru import logger

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

# Envelope da Região Metropolitana do Recife, com folga. Um destino fora disso
# não é atendido por ônibus da RMR e é melhor recusar do que traçar uma viagem
# impossível.
RMR_BBOX = (-9.0, -7.0, -36.0, -34.0)  # min_lat, max_lat, min_lon, max_lon


@dataclass(frozen=True)
class Place:
    latitude: float
    longitude: float
    endereco: str

    def as_dict(self) -> dict:
        return {
            "endereco": self.endereco,
            "latitude": self.latitude,
            "longitude": self.longitude,
        }


def _within_rmr(latitude: float, longitude: float) -> bool:
    min_lat, max_lat, min_lon, max_lon = RMR_BBOX
    return min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon


class GeocodingService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=15.0)
        return self._client

    async def geocode(self, endereco: str) -> Place | None:
        """Resolve um destino livre. Devolve None quando não dá para confiar."""
        if not self.api_key:
            logger.warning("Sem GOOGLE_MAPS_API_KEY — geocoding indisponível")
            return None
        if not endereco or not endereco.strip():
            return None

        params = {
            "address": endereco.strip(),
            "key": self.api_key,
            "language": "pt-BR",
            "region": "br",
            # Sem isso, "Boa Viagem" pode resolver em qualquer estado do país.
            "components": "administrative_area:PE|country:BR",
        }

        try:
            client = await self._get_client()
            response = await client.get(GEOCODE_URL, params=params)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.error(f"Geocoding indisponível: {exc}")
            return None

        if response.status_code != 200:
            logger.warning(f"Geocoding erro {response.status_code}")
            return None

        data = response.json()
        status = data.get("status")
        if status != "OK":
            logger.info(f"Geocoding sem resultado para {endereco!r}: {status}")
            return None

        results = data.get("results") or []
        if not results:
            return None

        top = results[0]
        location = (top.get("geometry") or {}).get("location") or {}
        latitude, longitude = location.get("lat"), location.get("lng")
        if latitude is None or longitude is None:
            return None

        if not _within_rmr(latitude, longitude):
            logger.info(
                f"Destino {endereco!r} caiu fora da RMR ({latitude}, {longitude})"
            )
            return None

        return Place(
            latitude=latitude,
            longitude=longitude,
            endereco=top.get("formatted_address") or endereco.strip(),
        )

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
