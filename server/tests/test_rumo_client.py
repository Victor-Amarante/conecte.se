"""RUMO HTTP client behaviour, with the network mocked.

Two quirks are load-bearing and easy to regress: the trailing slash that
``json_paradas_linha``/``json_shape`` require, and the retry that keeps a
1600-request sync from dying on one flaky response.
"""

import httpx
import pytest
import respx

from app.etl.rumo_client import RumoClient

BASE = "https://rumo.test/rumo"


@pytest.fixture
async def client():
    rumo = RumoClient(base_url=BASE, max_concurrency=2, timeout=5.0)
    yield rumo
    await rumo.close()


@respx.mock
async def test_fetch_lines_parses_the_home_page(client, fixture_text):
    respx.get(f"{BASE}/").mock(
        return_value=httpx.Response(200, text=fixture_text("rumo_home.html"))
    )

    lines = await client.fetch_lines()

    assert lines[0].codigo_linha == "001"
    assert len(lines) == 11


@respx.mock
async def test_fetch_sublines_passes_the_line_code(client, fixture_text):
    route = respx.get(f"{BASE}/").mock(
        return_value=httpx.Response(200, text=fixture_text("rumo_linha_011.html"))
    )

    sublines = await client.fetch_sublines("011")

    assert route.calls.last.request.url.params["codigo-linha"] == "011"
    assert [s.id for s in sublines] == [705, 706, 1120, 1473]


@respx.mock
async def test_itinerary_uses_a_trailing_slash(client, fixture_json):
    """Without the slash RUMO answers 301 and the payload is lost."""
    route = respx.get(f"{BASE}/json_paradas_linha/").mock(
        return_value=httpx.Response(
            200, json=fixture_json("json_paradas_linha_1424.json")
        )
    )

    rows = await client.fetch_subline_stops(1424)

    assert route.called
    assert route.calls.last.request.url.path.endswith("/json_paradas_linha/")
    assert rows[0]["sublinha"] == 1424


@respx.mock
async def test_shape_uses_a_trailing_slash(client, fixture_json):
    route = respx.get(f"{BASE}/json_shape/").mock(
        return_value=httpx.Response(200, json=fixture_json("json_shape_1424.json"))
    )

    await client.fetch_subline_shape(1424)

    assert route.calls.last.request.url.path.endswith("/json_shape/")


@respx.mock
async def test_redirects_are_followed(client, fixture_json):
    """Belt and braces: a 301 from RUMO must still yield the payload."""
    respx.get(f"{BASE}/json_shape").mock(
        return_value=httpx.Response(301, headers={"Location": f"{BASE}/json_shape/"})
    )
    respx.get(f"{BASE}/json_shape/").mock(
        return_value=httpx.Response(200, json=[{"sublinha": 1424}])
    )

    rows = await client._get_json("/json_shape")

    assert rows == [{"sublinha": 1424}]


@respx.mock
async def test_stop_inventory_is_returned_whole(client, fixture_json):
    fixture = fixture_json("json_mapa_paradas.json")
    respx.get(f"{BASE}/json_mapa_paradas").mock(
        return_value=httpx.Response(200, json=fixture)
    )

    stops = await client.fetch_all_stops()

    assert len(stops) == len(fixture)
    assert {"id", "nombre", "posX", "posY", "clase", "nodo"} <= set(stops[0])


@respx.mock
async def test_transient_server_errors_are_retried(client):
    route = respx.get(f"{BASE}/json_mapa_paradas").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200, json=[{"id": 1}]),
        ]
    )

    stops = await client.fetch_all_stops()

    assert route.call_count == 2
    assert stops == [{"id": 1}]


@respx.mock
async def test_timeouts_are_retried(client):
    route = respx.get(f"{BASE}/json_mapa_paradas").mock(
        side_effect=[httpx.TimeoutException("slow"), httpx.Response(200, json=[])]
    )

    await client.fetch_all_stops()

    assert route.call_count == 2


@respx.mock
async def test_persistent_failure_eventually_raises(client):
    respx.get(f"{BASE}/json_mapa_paradas").mock(return_value=httpx.Response(500))

    with pytest.raises(httpx.HTTPStatusError):
        await client.fetch_all_stops()


@respx.mock
async def test_sends_an_identifiable_user_agent(client):
    route = respx.get(f"{BASE}/json_mapa_paradas").mock(
        return_value=httpx.Response(200, json=[])
    )

    await client.fetch_all_stops()

    assert "Conectese" in route.calls.last.request.headers["user-agent"]
