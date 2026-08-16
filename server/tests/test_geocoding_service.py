"""Resolução do destino escrito à mão."""

import httpx
import pytest
import respx

from app.services.geocoding_service import GeocodingService

GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def ok(lat: float, lon: float, endereco: str = "R. Padre Carapuceiro, 777 - Recife"):
    return {
        "status": "OK",
        "results": [
            {
                "formatted_address": endereco,
                "geometry": {"location": {"lat": lat, "lng": lon}},
            }
        ],
    }


@respx.mock
async def test_resolves_a_landmark():
    respx.get(GEOCODE_URL).mock(return_value=httpx.Response(200, json=ok(-8.119, -34.904)))
    service = GeocodingService(api_key="k")

    place = await service.geocode("Shopping Recife")

    assert place is not None
    assert place.latitude == pytest.approx(-8.119)
    assert "Recife" in place.endereco
    await service.close()


@respx.mock
async def test_biases_the_search_to_pernambuco():
    """Sem isso, "Boa Viagem" resolve em outros estados do país."""
    route = respx.get(GEOCODE_URL).mock(
        return_value=httpx.Response(200, json=ok(-8.119, -34.904))
    )
    service = GeocodingService(api_key="k")

    await service.geocode("Boa Viagem")

    params = route.calls.last.request.url.params
    assert "administrative_area:PE" in params["components"]
    assert params["region"] == "br"
    await service.close()


@respx.mock
async def test_rejects_a_destination_outside_the_metro_area():
    """São Paulo geocodifica bem, mas nenhum ônibus da RMR vai até lá."""
    respx.get(GEOCODE_URL).mock(
        return_value=httpx.Response(200, json=ok(-23.55, -46.63, "São Paulo - SP"))
    )
    service = GeocodingService(api_key="k")

    assert await service.geocode("Avenida Paulista") is None
    await service.close()


@respx.mock
async def test_zero_results_returns_none():
    respx.get(GEOCODE_URL).mock(
        return_value=httpx.Response(200, json={"status": "ZERO_RESULTS", "results": []})
    )
    service = GeocodingService(api_key="k")

    assert await service.geocode("lugar aquele lá") is None
    await service.close()


@respx.mock
async def test_api_error_returns_none():
    respx.get(GEOCODE_URL).mock(return_value=httpx.Response(403, text="denied"))
    service = GeocodingService(api_key="k")

    assert await service.geocode("Marco Zero") is None
    await service.close()


@respx.mock
async def test_timeout_returns_none():
    respx.get(GEOCODE_URL).mock(side_effect=httpx.TimeoutException("slow"))
    service = GeocodingService(api_key="k")

    assert await service.geocode("Marco Zero") is None
    await service.close()


async def test_empty_input_short_circuits():
    service = GeocodingService(api_key="k")

    assert await service.geocode("") is None
    assert await service.geocode("   ") is None
    await service.close()


@respx.mock
async def test_without_a_key_nothing_is_called():
    route = respx.get(GEOCODE_URL)
    service = GeocodingService(api_key="")

    assert await service.geocode("Marco Zero") is None
    assert not route.called
    await service.close()
