"""Planeja a viagem de ônibus entre onde o passageiro está e onde quer chegar.

Esta é a pergunta certa a fazer ao Google. Antes perguntávamos "quando passa a
linha X nesta parada?", e a Routes API — que otimiza a viagem mais rápida entre
dois pontos — frequentemente respondia com outra linha. Perguntando
origem → destino, a resposta do Google **é** o que o passageiro precisa: qual
linha pegar, em que parada embarcar, a que horas e onde baldear.

O que o Google não sabe é o nome da parada em linguagem de quem mora aqui. Ele
devolve "Av. Prof. Artur de Sá, 577-603"; a base do RUMO tem "PARADA 15 - EM
FRENTE AO Nº4403 (EDF. MARIA DULCE)". Por isso cada embarque é enriquecido com
a parada mais próxima do nosso banco.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.departure_service import RECIFE_TZ, _parse_time

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"

FIELD_MASK = ",".join(
    [
        "routes.duration",
        "routes.legs.steps.transitDetails",
        "routes.legs.steps.travelMode",
        "routes.legs.steps.distanceMeters",
    ]
)

# Além disso o trajeto deixa de ser "pegar um ônibus" e vira uma odisseia; é
# melhor dizer que não achamos algo razoável.
MAX_TRANSFERS = 2


@dataclass
class TransitLeg:
    """Um trecho de ônibus da viagem."""

    codigo_linha: str
    nome_linha: str | None
    sentido: str | None
    embarque: str | None
    embarque_lat: float | None
    embarque_lon: float | None
    desembarque: str | None
    partida: datetime | None
    chegada: datetime | None
    paradas: int | None
    # Preenchido a partir do nosso banco, quando encontramos a parada.
    parada_conhecida: dict | None = None

    @property
    def faltam_minutos(self) -> int | None:
        if self.partida is None:
            return None
        delta = self.partida - datetime.now(timezone.utc)
        return max(0, int(delta.total_seconds() // 60))

    def _hhmm(self, value: datetime | None) -> str | None:
        return value.astimezone(RECIFE_TZ).strftime("%H:%M") if value else None

    def as_dict(self) -> dict:
        dados = {
            "codigo_linha": self.codigo_linha,
            "nome_linha": self.nome_linha,
            "sentido": self.sentido,
            "embarque": self.embarque,
            "desembarque": self.desembarque,
            "horario_partida": self._hhmm(self.partida),
            "horario_chegada": self._hhmm(self.chegada),
            "faltam_minutos": self.faltam_minutos,
            "paradas_no_trecho": self.paradas,
        }
        if self.parada_conhecida:
            dados["parada"] = self.parada_conhecida
        return dados


@dataclass
class JourneyResult:
    """Resultado do planejamento.

    ``a_pe_metros`` é preenchido quando o Google não sugere ônibus algum porque
    o destino está perto demais. Sem distinguir esse caso de "não achei rota",
    o passageiro ouviria "não encontrei" para um trajeto de 10 minutos a pé.
    """

    journeys: list["Journey"] = field(default_factory=list)
    a_pe_metros: int | None = None
    a_pe_minutos: int | None = None

    @property
    def vazio(self) -> bool:
        return not self.journeys and self.a_pe_metros is None


@dataclass
class Journey:
    """Uma opção completa de viagem."""

    legs: list[TransitLeg] = field(default_factory=list)
    duracao_total_minutos: int | None = None
    caminhada_metros: int = 0

    @property
    def baldeacoes(self) -> int:
        return max(0, len(self.legs) - 1)

    def as_dict(self) -> dict:
        return {
            "duracao_total_minutos": self.duracao_total_minutos,
            "baldeacoes": self.baldeacoes,
            "caminhada_metros": self.caminhada_metros,
            "trechos": [leg.as_dict() for leg in self.legs],
        }


class JourneyService:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=25.0)
        return self._client

    async def plan(
        self,
        *,
        origin_lat: float,
        origin_lon: float,
        destination_lat: float,
        destination_lon: float,
        max_options: int = 3,
    ) -> JourneyResult:
        if not self.api_key:
            logger.warning("Sem GOOGLE_MAPS_API_KEY — não é possível planejar viagem")
            return JourneyResult()

        payload = {
            "origin": {
                "location": {
                    "latLng": {"latitude": origin_lat, "longitude": origin_lon}
                }
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
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        try:
            client = await self._get_client()
            response = await client.post(ROUTES_URL, json=payload, headers=headers)
        except (httpx.TimeoutException, httpx.RequestError) as exc:
            logger.error(f"Routes API (viagem) indisponível: {exc}")
            return JourneyResult()

        if response.status_code != 200:
            logger.warning(
                f"Routes API (viagem) erro {response.status_code}: "
                f"{response.text[:200]}"
            )
            return JourneyResult()

        return self._parse(response.json(), max_options)

    @staticmethod
    def _parse(data: dict, max_options: int) -> JourneyResult:
        journeys: list[Journey] = []
        somente_a_pe: Journey | None = None

        for route in data.get("routes", []):
            journey = Journey()

            duracao = route.get("duration")
            if duracao:
                try:
                    journey.duracao_total_minutos = max(
                        1, int(round(float(str(duracao).rstrip("s")) / 60))
                    )
                except ValueError:
                    pass

            for leg in route.get("legs", []):
                for step in leg.get("steps", []):
                    if step.get("travelMode") == "WALK":
                        journey.caminhada_metros += step.get("distanceMeters") or 0
                        continue

                    details = step.get("transitDetails")
                    if not details:
                        continue

                    line = details.get("transitLine", {})
                    codigo = line.get("nameShort") or line.get("name")
                    if not codigo:
                        continue

                    stops = details.get("stopDetails", {})
                    embarque = stops.get("departureStop") or {}
                    desembarque = stops.get("arrivalStop") or {}
                    local = embarque.get("location", {}).get("latLng", {})

                    journey.legs.append(
                        TransitLeg(
                            codigo_linha=codigo.strip(),
                            nome_linha=line.get("name"),
                            sentido=details.get("headsign"),
                            embarque=embarque.get("name"),
                            embarque_lat=local.get("latitude"),
                            embarque_lon=local.get("longitude"),
                            desembarque=desembarque.get("name"),
                            partida=_parse_time(stops.get("departureTime")),
                            chegada=_parse_time(stops.get("arrivalTime")),
                            paradas=details.get("stopCount"),
                        )
                    )

            if not journey.legs:
                # Rota inteiramente a pé: o destino está perto demais para o
                # Google sugerir ônibus. Guardamos a mais curta para poder
                # dizer isso, em vez de responder "não encontrei".
                if somente_a_pe is None or (
                    journey.caminhada_metros < somente_a_pe.caminhada_metros
                ):
                    somente_a_pe = journey
                continue
            if journey.baldeacoes > MAX_TRANSFERS:
                continue

            journeys.append(journey)

        # Menos baldeação primeiro; entre iguais, a mais rápida.
        journeys.sort(
            key=lambda j: (j.baldeacoes, j.duracao_total_minutos or 10**6)
        )

        if journeys:
            return JourneyResult(journeys=journeys[:max_options])
        if somente_a_pe is not None:
            return JourneyResult(
                a_pe_metros=somente_a_pe.caminhada_metros,
                a_pe_minutos=somente_a_pe.duracao_total_minutos,
            )
        return JourneyResult()

    async def enrich_stops(
        self, session: AsyncSession, journeys: list[Journey]
    ) -> None:
        """Casa cada embarque com a parada equivalente no nosso banco.

        O Google identifica a parada por endereço; o passageiro reconhece pela
        referência do RUMO ("EM FRENTE AO Nº4403"). Sem isso ele sabe que linha
        pegar mas não onde ficar esperando.
        """
        for journey in journeys:
            for leg in journey.legs:
                if leg.embarque_lat is None or leg.embarque_lon is None:
                    continue
                result = await session.execute(
                    text(
                        """
                        SELECT s.codigo, s.nome, s.referencia,
                               ST_Distance(
                                   s.geom::geography,
                                   ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                               ) AS distancia
                        FROM line_stop_index lsi
                        JOIN stops s ON s.id = lsi.stop_id
                        WHERE lsi.codigo_linha = :codigo
                          AND ST_DWithin(
                              s.geom::geography,
                              ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                              250
                          )
                        ORDER BY distancia
                        LIMIT 1
                        """
                    ),
                    {
                        "codigo": leg.codigo_linha,
                        "lat": leg.embarque_lat,
                        "lon": leg.embarque_lon,
                    },
                )
                row = result.first()
                if row is None:
                    continue
                leg.parada_conhecida = {
                    "codigo": row.codigo,
                    "nome": row.nome or row.codigo,
                    "referencia": row.referencia,
                }

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
