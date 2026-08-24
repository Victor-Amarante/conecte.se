"""Planejamento de viagem origem → destino.

Perguntar "como chego em X" é a pergunta certa a fazer à Routes API: ela otimiza
a viagem entre dois pontos, então a resposta já é a linha que o passageiro
precisa. Os payloads abaixo têm o formato real devolvido para o Recife.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.services.journey_service import JourneyService

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def transit_step(codigo: str, partida: str, chegada: str, embarque="Av. X, 100"):
    return {
        "travelMode": "TRANSIT",
        "transitDetails": {
            "transitLine": {"nameShort": codigo, "name": f"Linha {codigo}"},
            "headsign": "Centro",
            "stopCount": 20,
            "stopDetails": {
                "departureStop": {
                    "name": embarque,
                    "location": {"latLng": {"latitude": -8.12, "longitude": -34.90}},
                },
                "departureTime": partida,
                "arrivalStop": {"name": "Destino"},
                "arrivalTime": chegada,
            },
        },
    }


def walk_step(metros: int):
    return {"travelMode": "WALK", "distanceMeters": metros}


def route(*steps, duration="2760s"):
    return {"duration": duration, "legs": [{"steps": list(steps)}]}


def response(*routes_):
    return {"routes": list(routes_)}


class TestParsing:
    def test_reads_a_direct_trip(self):
        data = response(
            route(
                walk_step(300),
                transit_step("062", "2026-08-16T15:35:00Z", "2026-08-16T15:56:00Z"),
                walk_step(120),
            )
        )

        result = JourneyService._parse(data, 3)

        assert len(result.journeys) == 1
        journey = result.journeys[0]
        assert journey.baldeacoes == 0
        assert journey.caminhada_metros == 420
        assert journey.duracao_total_minutos == 46
        assert journey.legs[0].codigo_linha == "062"

    def test_reads_a_trip_with_a_transfer(self):
        data = response(
            route(
                transit_step("155", "2026-08-16T15:31:00Z", "2026-08-16T15:55:00Z"),
                walk_step(80),
                transit_step("102", "2026-08-16T15:58:00Z", "2026-08-16T16:03:00Z"),
            )
        )

        result = JourneyService._parse(data, 3)

        assert result.journeys[0].baldeacoes == 1
        assert [l.codigo_linha for l in result.journeys[0].legs] == ["155", "102"]

    def test_direct_trips_outrank_transfers(self):
        """Menos baldeação vence, mesmo que a viagem demore um pouco mais."""
        com_baldeacao = route(
            transit_step("155", "2026-08-16T15:31:00Z", "2026-08-16T15:55:00Z"),
            transit_step("102", "2026-08-16T15:58:00Z", "2026-08-16T16:03:00Z"),
            duration="1800s",
        )
        direta = route(
            transit_step("062", "2026-08-16T15:35:00Z", "2026-08-16T16:10:00Z"),
            duration="2400s",
        )

        result = JourneyService._parse(response(com_baldeacao, direta), 3)

        assert result.journeys[0].legs[0].codigo_linha == "062"

    def test_drops_trips_with_too_many_transfers(self):
        data = response(
            route(
                transit_step("1", "2026-08-16T15:00:00Z", "2026-08-16T15:10:00Z"),
                transit_step("2", "2026-08-16T15:12:00Z", "2026-08-16T15:20:00Z"),
                transit_step("3", "2026-08-16T15:22:00Z", "2026-08-16T15:30:00Z"),
                transit_step("4", "2026-08-16T15:32:00Z", "2026-08-16T15:40:00Z"),
            )
        )

        assert JourneyService._parse(data, 3).journeys == []

    def test_respects_the_option_cap(self):
        data = response(
            *[
                route(transit_step(str(i), "2026-08-16T15:00:00Z", "2026-08-16T15:30:00Z"))
                for i in range(6)
            ]
        )

        assert len(JourneyService._parse(data, 3).journeys) == 3


class TestWalkingDistance:
    """Um destino a 800 m não gera trecho de ônibus.

    Sem distinguir esse caso, o passageiro ouviria "não encontrei rota" para um
    trajeto de 10 minutos a pé — pior que inútil, é enganoso.
    """

    def test_walk_only_is_reported_as_such(self):
        data = response(route(walk_step(850), duration="960s"))

        result = JourneyService._parse(data, 3)

        assert result.journeys == []
        assert result.a_pe_metros == 850
        assert result.a_pe_minutos == 16
        assert not result.vazio

    def test_the_shortest_walk_is_kept(self):
        data = response(
            route(walk_step(1200), duration="900s"),
            route(walk_step(850), duration="960s"),
        )

        assert JourneyService._parse(data, 3).a_pe_metros == 850

    def test_a_bus_trip_wins_over_a_walk_only_alternative(self):
        data = response(
            route(walk_step(2000), duration="1800s"),
            route(transit_step("062", "2026-08-16T15:35:00Z", "2026-08-16T15:56:00Z")),
        )

        result = JourneyService._parse(data, 3)

        assert len(result.journeys) == 1
        assert result.a_pe_metros is None

    def test_nothing_at_all_is_empty(self):
        result = JourneyService._parse({"routes": []}, 3)

        assert result.vazio


class TestLegFields:
    def test_minutes_until_departure(self):
        soon = datetime.now(timezone.utc) + timedelta(minutes=15)
        data = response(
            route(
                transit_step(
                    "062",
                    soon.isoformat().replace("+00:00", "Z"),
                    "2026-08-16T15:56:00Z",
                )
            )
        )

        leg = JourneyService._parse(data, 1).journeys[0].legs[0]

        assert leg.faltam_minutos in (14, 15)

    def test_times_are_local(self):
        data = response(
            route(transit_step("062", "2026-08-16T15:35:00Z", "2026-08-16T15:56:00Z"))
        )

        leg = JourneyService._parse(data, 1).journeys[0].legs[0].as_dict()

        assert leg["horario_partida"] == "12:35"  # UTC-3
        assert leg["horario_chegada"] == "12:56"


class TestRequest:
    @respx.mock
    async def test_asks_for_transit_by_bus(self):
        route_mock = respx.post(ROUTES_URL).mock(
            return_value=httpx.Response(
                200,
                json=response(
                    route(
                        transit_step(
                            "062", "2026-08-16T15:35:00Z", "2026-08-16T15:56:00Z"
                        )
                    )
                ),
            )
        )
        service = JourneyService(api_key="k")

        await service.plan(
            origin_lat=-8.12, origin_lon=-34.90,
            destination_lat=-8.06, destination_lon=-34.87,
        )

        body = route_mock.calls.last.request.read().decode()
        assert "TRANSIT" in body and "BUS" in body
        await service.close()

    @respx.mock
    async def test_errors_degrade_to_empty(self):
        respx.post(ROUTES_URL).mock(return_value=httpx.Response(500))
        service = JourneyService(api_key="k")

        result = await service.plan(
            origin_lat=-8.12, origin_lon=-34.90,
            destination_lat=-8.06, destination_lon=-34.87,
        )

        assert result.vazio
        await service.close()

    @respx.mock
    async def test_without_a_key_nothing_is_called(self):
        route_mock = respx.post(ROUTES_URL)
        service = JourneyService(api_key="")

        result = await service.plan(
            origin_lat=-8.12, origin_lon=-34.90,
            destination_lat=-8.06, destination_lon=-34.87,
        )

        assert result.vazio
        assert not route_mock.called
        await service.close()
