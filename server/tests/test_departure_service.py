"""Leitura das partidas de transporte público retornadas pela Routes API.

Os payloads abaixo têm o formato exato que o Google devolveu para o Recife —
inclusive os códigos de linha do Grande Recife, que coincidem com os do RUMO e
são o que permite cruzar as duas fontes.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
import respx

from app.services.departure_service import RECIFE_TZ, DepartureService

ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def leg(line_short: str, departure: str, headsign: str = "Centro", stop="Parada X"):
    return {
        "steps": [
            {
                "transitDetails": {
                    "transitLine": {
                        "nameShort": line_short,
                        "name": f"Linha {line_short}",
                        "agencies": [{"name": "Grande Recife Consórcio de Transporte"}],
                        "vehicle": {"type": "BUS"},
                    },
                    "headsign": headsign,
                    "stopCount": 12,
                    "stopDetails": {
                        "departureStop": {"name": stop},
                        "departureTime": departure,
                        "arrivalStop": {"name": "Destino"},
                        "arrivalTime": departure,
                    },
                }
            }
        ]
    }


def response(*legs_):
    return {"routes": [{"legs": [lg]} for lg in legs_]}


class TestParsing:
    def test_reads_line_time_and_headsign(self):
        data = response(leg("2462", "2026-08-13T03:02:47Z", "Bacurau", "Av. Artur de Sá"))

        deps = DepartureService._parse(data, None, 3)

        assert len(deps) == 1
        assert deps[0].codigo_linha == "2462"
        assert deps[0].headsign == "Bacurau"
        assert deps[0].stop_name == "Av. Artur de Sá"

    def test_filters_by_the_chosen_line(self):
        """Rotas alternativas trazem outras linhas; só a escolhida interessa."""
        data = response(
            leg("1927", "2026-08-13T03:00:00Z"),
            leg("2462", "2026-08-13T03:02:00Z"),
            leg("424", "2026-08-13T03:05:00Z"),
        )

        deps = DepartureService._parse(data, "2462", 5)

        assert [d.codigo_linha for d in deps] == ["2462"]

    def test_without_a_filter_returns_every_line(self):
        data = response(
            leg("1927", "2026-08-13T03:00:00Z"), leg("2462", "2026-08-13T03:02:00Z")
        )

        assert len(DepartureService._parse(data, None, 5)) == 2

    def test_deduplicates_the_same_departure_across_alternatives(self):
        """O Google repete o mesmo embarque em rotas alternativas."""
        data = response(
            leg("2462", "2026-08-13T03:02:47Z"),
            leg("2462", "2026-08-13T03:02:47Z"),
            leg("2462", "2026-08-13T03:32:00Z"),
        )

        deps = DepartureService._parse(data, "2462", 5)

        assert len(deps) == 2

    def test_sorted_by_time_and_capped(self):
        data = response(
            leg("2462", "2026-08-13T04:00:00Z"),
            leg("2462", "2026-08-13T03:00:00Z"),
            leg("2462", "2026-08-13T03:30:00Z"),
        )

        deps = DepartureService._parse(data, "2462", 2)

        assert len(deps) == 2
        assert deps[0].departure_time < deps[1].departure_time

    def test_ignores_walking_steps(self):
        data = {"routes": [{"legs": [{"steps": [{"navigationInstruction": {}}]}]}]}

        assert DepartureService._parse(data, None, 3) == []

    def test_ignores_entries_without_a_departure_time(self):
        broken = leg("2462", "2026-08-13T03:00:00Z")
        del broken["steps"][0]["transitDetails"]["stopDetails"]["departureTime"]

        assert DepartureService._parse(response(broken), None, 3) == []

    def test_falls_back_to_the_long_name_when_short_is_absent(self):
        data = response(leg("2462", "2026-08-13T03:00:00Z"))
        del data["routes"][0]["legs"][0]["steps"][0]["transitDetails"]["transitLine"][
            "nameShort"
        ]

        deps = DepartureService._parse(data, None, 3)

        assert deps[0].codigo_linha == "Linha 2462"


class TestDepartureFields:
    def test_minutes_from_now_counts_forward(self):
        soon = datetime.now(timezone.utc) + timedelta(minutes=18)
        data = response(leg("2462", soon.isoformat().replace("+00:00", "Z")))

        deps = DepartureService._parse(data, None, 1)

        assert deps[0].minutes_from_now in (17, 18)

    def test_a_past_departure_never_goes_negative(self):
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        data = response(leg("2462", past.isoformat().replace("+00:00", "Z")))

        assert DepartureService._parse(data, None, 1)[0].minutes_from_now == 0

    def test_time_is_shown_in_recife_local_time(self):
        """O Google responde em UTC; o passageiro pensa em horário do Recife."""
        data = response(leg("2462", "2026-08-13T03:02:47Z"))

        assert DepartureService._parse(data, None, 1)[0].local_time == "00:02"

    def test_recife_is_utc_minus_three(self):
        assert RECIFE_TZ.utcoffset(None) == timedelta(hours=-3)


class TestRequest:
    @respx.mock
    async def test_asks_for_transit_by_bus(self):
        route = respx.post(ROUTES_URL).mock(
            return_value=httpx.Response(200, json=response(leg("2462", "2026-08-13T03:00:00Z")))
        )
        service = DepartureService(api_key="k")

        await service.next_departures(
            origin_lat=-8.04, origin_lon=-34.95,
            destination_lat=-8.06, destination_lon=-34.87,
            codigo_linha="2462",
        )

        body = route.calls.last.request.read().decode()
        assert '"travelMode": "TRANSIT"' in body or '"travelMode":"TRANSIT"' in body
        assert "BUS" in body
        await service.close()

    @respx.mock
    async def test_no_api_key_means_no_call_and_no_crash(self):
        route = respx.post(ROUTES_URL)
        service = DepartureService(api_key="")

        result = await service.next_departures(
            origin_lat=-8.04, origin_lon=-34.95,
            destination_lat=-8.06, destination_lon=-34.87,
        )

        assert result == []
        assert not route.called
        await service.close()

    @respx.mock
    async def test_api_errors_degrade_to_an_empty_list(self):
        respx.post(ROUTES_URL).mock(return_value=httpx.Response(403, text="denied"))
        service = DepartureService(api_key="k")

        assert await service.next_departures(
            origin_lat=-8.04, origin_lon=-34.95,
            destination_lat=-8.06, destination_lon=-34.87,
        ) == []
        await service.close()

    @respx.mock
    async def test_timeouts_degrade_to_an_empty_list(self):
        respx.post(ROUTES_URL).mock(side_effect=httpx.TimeoutException("slow"))
        service = DepartureService(api_key="k")

        assert await service.next_departures(
            origin_lat=-8.04, origin_lon=-34.95,
            destination_lat=-8.06, destination_lon=-34.87,
        ) == []
        await service.close()
