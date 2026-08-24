"""Linhas diretas calculadas nos nossos próprios itinerários.

Existe para o caso em que o Google se recusa a sugerir ônibus por achar o
trajeto curto demais. O passageiro pode querer o ônibus mesmo assim — bagagem,
criança no colo, chuva, sol — e "vá a pé" não é resposta para quem pediu ônibus.

Precisa de banco com os dados do RUMO carregados.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.services.transit_service import transit_service

# Av. Boa Viagem -> Shopping Recife: ~850 m, curto o bastante para o Google
# responder "vá a pé", mas servido por várias linhas.
ORIGEM = (-8.126351356506348, -34.90253448486328)
DESTINO = (-8.1190456, -34.9046689)

pytestmark = pytest.mark.integration


@pytest.fixture
async def session():
    engine = create_async_engine(settings.conectese_database_url, poolclass=NullPool)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            try:
                count = await db.scalar(text("SELECT COUNT(*) FROM stops"))
            except (OperationalError, DBAPIError, OSError) as exc:
                pytest.skip(f"database unavailable: {exc}")
            if not count:
                pytest.skip("transit data not loaded — run the ETL first")
            yield db
    finally:
        await engine.dispose()


async def test_finds_direct_lines_for_a_short_trip(session):
    linhas = await transit_service.find_direct_lines(
        session,
        origin_lat=ORIGEM[0], origin_lon=ORIGEM[1],
        destination_lat=DESTINO[0], destination_lon=DESTINO[1],
    )

    assert linhas, "trajeto conhecido deveria ter linha direta"
    for linha in linhas:
        assert linha["codigo_linha"]
        assert linha["parada_embarque"]["distancia_m"] >= 0
        assert linha["paradas_no_trecho"] >= 1


async def test_the_most_direct_line_comes_first(session):
    """Ordenar só por parada mais próxima colocaria em primeiro uma linha que
    passa na esquina mas dá a volta inteira — 80 paradas para andar 800 m."""
    linhas = await transit_service.find_direct_lines(
        session,
        origin_lat=ORIGEM[0], origin_lon=ORIGEM[1],
        destination_lat=DESTINO[0], destination_lon=DESTINO[1],
    )
    if len(linhas) < 2:
        pytest.skip("poucas linhas para comparar")

    paradas = [l["paradas_no_trecho"] for l in linhas]
    assert paradas == sorted(paradas)
    assert paradas[0] <= 10, "a primeira opção deveria ser realmente direta"


async def test_never_suggests_the_wrong_direction(session):
    """A parada de destino tem que vir DEPOIS da de embarque no itinerário.

    Sem essa comparação sugeriríamos a linha certa no sentido oposto, que é
    pior do que não sugerir nada.
    """
    ida = await transit_service.find_direct_lines(
        session,
        origin_lat=ORIGEM[0], origin_lon=ORIGEM[1],
        destination_lat=DESTINO[0], destination_lon=DESTINO[1],
    )
    volta = await transit_service.find_direct_lines(
        session,
        origin_lat=DESTINO[0], origin_lon=DESTINO[1],
        destination_lat=ORIGEM[0], destination_lon=ORIGEM[1],
    )

    # Um trecho só faz sentido num sentido do itinerário; as duas listas não
    # podem ser idênticas, senão a ordem das paradas não estaria sendo usada.
    assert {l["codigo_linha"] for l in ida} != {l["codigo_linha"] for l in volta}


async def test_the_boarding_stop_carries_a_street_reference(session):
    """Saber a linha sem saber onde esperar não resolve o problema."""
    linhas = await transit_service.find_direct_lines(
        session,
        origin_lat=ORIGEM[0], origin_lon=ORIGEM[1],
        destination_lat=DESTINO[0], destination_lon=DESTINO[1],
    )

    assert any(l["parada_embarque"].get("referencia") for l in linhas)


async def test_no_lines_between_unconnected_points(session):
    linhas = await transit_service.find_direct_lines(
        session,
        origin_lat=-8.0, origin_lon=-30.0,   # em alto-mar
        destination_lat=DESTINO[0], destination_lon=DESTINO[1],
    )

    assert linhas == []


async def test_respects_the_limit(session):
    linhas = await transit_service.find_direct_lines(
        session,
        origin_lat=ORIGEM[0], origin_lon=ORIGEM[1],
        destination_lat=DESTINO[0], destination_lon=DESTINO[1],
        limit=2,
    )

    assert len(linhas) <= 2
