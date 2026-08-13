"""Quando o próximo ônibus de uma linha passa na parada do usuário.

O Google Maps tem cobertura de transporte público do Grande Recife e usa **os
mesmos códigos de linha** do RUMO ("2462", "1927", ...), então as duas fontes
se encaixam sem tradução:

* o RUMO (no nosso Postgres) diz **quais linhas atendem o usuário e onde ficam
  as paradas** — consulta espacial local, instantânea;
* o Google diz **quando o veículo passa** — sem exigir que exista um rastreador
  GPS próprio em cada ônibus.

A Routes API não responde "próximas partidas na parada X"; ela calcula rotas
entre dois pontos. Contornamos isso pedindo uma rota da parada do usuário até
uma parada adiante **no itinerário da mesma linha**, e filtrando os trechos
cuja linha bate com a escolhida. O itinerário vem do RUMO, que já temos.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx
from loguru import logger

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

FIELD_MASK = ",".join(
    [
        "routes.legs.steps.transitDetails.transitLine.nameShort",
        "routes.legs.steps.transitDetails.transitLine.name",
        "routes.legs.steps.transitDetails.transitLine.agencies.name",
        "routes.legs.steps.transitDetails.transitLine.vehicle.type",
        "routes.legs.steps.transitDetails.stopDetails",
        "routes.legs.steps.transitDetails.headsign",
        "routes.legs.steps.transitDetails.stopCount",
    ]
)

# Fuso do Recife. Sem horário de verão desde 2019, então o offset é fixo.
RECIFE_TZ = timezone(timedelta(hours=-3))

# Quantas paradas adiante usar como destino. Longe o bastante para o Google
# preferir seguir a própria linha em vez de sugerir uma baldeação curta.
DOWNSTREAM_STOPS_AHEAD = 12


@dataclass(frozen=True)
class Departure:
    codigo_linha: str
    nome_linha: str | None
    headsign: str | None
    stop_name: str | None
    departure_time: datetime
    stop_count: int | None

    @property
    def minutes_from_now(self) -> int:
        delta = self.departure_time - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds() // 60))

    @property
    def local_time(self) -> str:
        return self.departure_time.astimezone(RECIFE_TZ).strftime("%H:%M")

    def as_dict(self) -> dict:
        return {
            "codigo_linha": self.codigo_linha,
            "sentido": self.headsign,
            "parada": self.stop_name,
            "horario": self.local_time,
            "faltam_minutos": self.minutes_from_now,
        }


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class DepartureService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def next_departures(
        self,
        *,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        codigo_linha: str | None = None,
        depart_after: datetime | None = None,
        max_results: int = 3,
    ) -> list[Departure]:
        """Próximas partidas entre dois pontos, opcionalmente filtradas por linha."""
        if not self.api_key:
            logger.warning("Sem GOOGLE_MAPS_API_KEY — não é possível consultar partidas")
            return []

        payload = {
            "origin": {
                "location": {"latLng": {"latitude": origin_lat, "longitude": origin_lon}}
            },
            "destination": {
                "location": {
                    "latLng": {
                        "latitude": destination_lat,
                        "longitude": destination_lon,
                    }
                }
            },
            "travelMode": "TRANSIT",
            "computeAlternativeRoutes": True,
            "transitPreferences": {"allowedTravelModes": ["BUS"]},
            "languageCode": "pt-BR",
            "units": "METRIC",
        }
        if depart_after is not None:
            payload["departureTime"] = (
                depart_after.astimezone(timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        try:
            client = await self._get_client()
            response = await client.post(ROUTES_URL, json=payload, headers=headers)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.error(f"Routes API (TRANSIT) indisponível: {exc}")
            return []

        if response.status_code != 200:
            logger.warning(
                f"Routes API (TRANSIT) erro {response.status_code}: "
                f"{response.text[:200]}"
            )
            return []

        return self._parse(response.json(), codigo_linha, max_results)

    @staticmethod
    def _parse(
        data: dict, codigo_linha: str | None, max_results: int
    ) -> list[Departure]:
        departures: list[Departure] = []
        seen: set[tuple[str, str]] = set()

        for route in data.get("routes", []):
            for leg in route.get("legs", []):
                for step in leg.get("steps", []):
                    details = step.get("transitDetails")
                    if not details:
                        continue

                    line = details.get("transitLine", {})
                    codigo = line.get("nameShort") or line.get("name")
                    if not codigo:
                        continue
                    if codigo_linha and codigo.strip() != codigo_linha.strip():
                        continue

                    stops = details.get("stopDetails", {})
                    departure_time = _parse_time(stops.get("departureTime"))
                    if departure_time is None:
                        continue

                    # Rotas alternativas repetem a mesma partida; a chave
                    # (linha, horário) desduplica sem perder partidas distintas.
                    key = (codigo, departure_time.isoformat())
                    if key in seen:
                        continue
                    seen.add(key)

                    departures.append(
                        Departure(
                            codigo_linha=codigo,
                            nome_linha=line.get("name"),
                            headsign=details.get("headsign"),
                            stop_name=(stops.get("departureStop") or {}).get("name"),
                            departure_time=departure_time,
                            stop_count=details.get("stopCount"),
                        )
                    )

        departures.sort(key=lambda d: d.departure_time)

        if codigo_linha:
            return departures[:max_results]

        # Sem filtro de linha a lista vira o cardápio do passageiro, e duas
        # partidas seguidas da mesma linha desperdiçariam vagas que poderiam
        # mostrar outra opção. Damos uma passagem por linha primeiro e só então
        # completamos com as repetições, ainda em ordem de horário.
        primeiras: list[Departure] = []
        repetidas: list[Departure] = []
        vistas: set[str] = set()
        for departure in departures:
            if departure.codigo_linha in vistas:
                repetidas.append(departure)
            else:
                vistas.add(departure.codigo_linha)
                primeiras.append(departure)

        selecionadas = primeiras[:max_results]
        if len(selecionadas) < max_results:
            selecionadas.extend(repetidas[: max_results - len(selecionadas)])
        selecionadas.sort(key=lambda d: d.departure_time)
        return selecionadas

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
