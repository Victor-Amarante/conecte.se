"""Async HTTP client for the RUMO portal (Grande Recife).

RUMO exposes an undocumented but public JSON API behind its Leaflet map. The
endpoints and their quirks are documented per method below; the two that matter
most are that ``json_paradas_linha`` and ``json_shape`` **require a trailing
slash** (Django's APPEND_SLASH answers 301 otherwise), and that all coordinates
come back as UTM zone 25S easting/northing, not lat/lon.
"""

import asyncio
from typing import Any

import httpx
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.etl.parsers import ParsedLine, ParsedSubline, parse_lines, parse_sublines

USER_AGENT = (
    "ConecteseBot/0.1 (+https://github.com/Victor-Amarante/conectese; "
    "public transit assistant for Recife)"
)

_RETRYABLE = (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError)


class RumoClient:
    def __init__(
        self,
        base_url: str | None = None,
        max_concurrency: int | None = None,
        timeout: float | None = None,
        request_delay: float | None = None,
    ) -> None:
        self.base_url = (base_url or settings.rumo_base_url).rstrip("/")
        self._semaphore = asyncio.Semaphore(
            max_concurrency or settings.rumo_max_concurrency
        )
        # RUMO starts refusing connections under sustained load — a full sync is
        # ~1600 requests, and running a few back to back gets the client
        # temporarily blocked. This paces us without meaningfully slowing a run.
        self._request_delay = (
            settings.rumo_request_delay_seconds
            if request_delay is None
            else request_delay
        )
        self._client = httpx.AsyncClient(
            timeout=timeout or settings.rumo_timeout_seconds,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        )

    async def __aenter__(self) -> "RumoClient":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        if not self._client.is_closed:
            await self._client.aclose()

    @retry(
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=1, min=1, max=20),
        reraise=True,
    )
    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        url = f"{self.base_url}{path}"
        async with self._semaphore:
            response = await self._client.get(url, params=params)
            if self._request_delay:
                await asyncio.sleep(self._request_delay)
        response.raise_for_status()
        return response

    async def _get_json(self, path: str, params: dict | None = None) -> Any:
        response = await self._get(path, params)
        return response.json()

    # ------------------------------------------------------------------
    # Catalogue (HTML)
    # ------------------------------------------------------------------

    async def fetch_lines(self) -> list[ParsedLine]:
        """Every line in the network, from the ``#sel_linha`` select."""
        response = await self._get("/")
        lines = parse_lines(response.text)
        logger.info(f"RUMO: fetched {len(lines)} lines")
        return lines

    async def fetch_sublines(self, codigo_linha: str) -> list[ParsedSubline]:
        """The sublines (route variants) of one line."""
        response = await self._get("/", params={"codigo-linha": codigo_linha})
        return parse_sublines(response.text)

    # ------------------------------------------------------------------
    # JSON endpoints
    # ------------------------------------------------------------------

    async def fetch_all_stops(self) -> list[dict]:
        """The complete stop inventory (~7k rows) in a single request.

        Rows look like::

            {"id": 358, "nombre": "010001", "posX": 292036.27, "posY": 9105626.47,
             "clase": 1, "nodo": 1001}

        ``posX``/``posY`` are UTM zone 25S metres.
        """
        data = await self._get_json("/json_mapa_paradas")
        logger.info(f"RUMO: fetched {len(data)} stops")
        return data

    async def fetch_subline_stops(self, subline_id: int) -> list[dict]:
        """A subline's ordered itinerary. Trailing slash is required."""
        return await self._get_json(
            "/json_paradas_linha/", params={"codigoSublinha": subline_id}
        )

    async def fetch_subline_shape(self, subline_id: int) -> list[dict]:
        """A subline's drawn route as ordered points. Trailing slash is required."""
        return await self._get_json(
            "/json_shape/", params={"codigoSublinha": subline_id}
        )

    async def fetch_stop_lines(self, codigo_parada: str) -> list[dict]:
        """Lines serving a stop, by stop code.

        Only used to spot-check the derived ``line_stop_index``: covering every
        stop this way would cost ~7k requests, while the subline itineraries
        give the same information in ~600.

        Careful: this endpoint's ``latitude``/``longitude`` fields are actually
        easting/northing, in that order — the names are wrong upstream.
        """
        return await self._get_json(
            "/json_modal_paradas", params={"codigo-parada": codigo_parada}
        )
