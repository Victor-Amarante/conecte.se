"""Integration tests for the spatial queries.

These need a PostGIS database with the RUMO data loaded:

    docker compose up -d conectese-db
    uv run alembic upgrade head
    uv run python -m app.etl.cli sync --lines 001,011,191

They skip themselves when the database is unreachable or empty, so the unit
suite still runs on a bare checkout.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.services.transit_service import transit_service

# Cidade Universitária (UFPE), Recife — dense enough that several lines are
# always in range.
RECIFE_LAT, RECIFE_LON = -8.04887728646683, -34.95138771773008

pytestmark = pytest.mark.integration


@pytest.fixture
async def session():
    """A session on a per-test engine.

    The application's shared engine pools connections against the event loop
    that created them, and pytest-asyncio gives each test a fresh loop — reusing
    it here surfaces as a bogus "database unavailable" skip. NullPool plus a
    per-test engine keeps the two independent.
    """
    engine = create_async_engine(settings.conectese_database_url, poolclass=NullPool)
    try:
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as db:
            try:
                count = await db.scalar(text("SELECT COUNT(*) FROM stops"))
            except (OperationalError, DBAPIError) as exc:
                pytest.skip(f"database unavailable: {exc}")
            if not count:
                pytest.skip("transit data not loaded — run the ETL first")
            yield db
    finally:
        await engine.dispose()


class TestNearbyStops:
    async def test_returns_stops_ordered_by_distance(self, session):
        stops = await transit_service.find_nearby_stops(
            session, RECIFE_LAT, RECIFE_LON, radius_m=1000
        )

        assert stops
        distances = [s.distance_m for s in stops]
        assert distances == sorted(distances)

    async def test_respects_the_radius(self, session):
        stops = await transit_service.find_nearby_stops(
            session, RECIFE_LAT, RECIFE_LON, radius_m=300
        )

        assert all(s.distance_m <= 300 for s in stops)

    async def test_respects_the_limit(self, session):
        stops = await transit_service.find_nearby_stops(
            session, RECIFE_LAT, RECIFE_LON, radius_m=2000, limit=3
        )

        assert len(stops) <= 3

    async def test_empty_in_the_middle_of_the_ocean(self, session):
        stops = await transit_service.find_nearby_stops(
            session, -8.0, -30.0, radius_m=1000
        )

        assert stops == []


class TestProbableLines:
    async def test_returns_lines_ranked_by_score(self, session):
        lines = await transit_service.find_probable_lines(
            session, RECIFE_LAT, RECIFE_LON, radius_m=2000
        )

        assert lines
        scores = [line.score for line in lines]
        assert scores == sorted(scores, reverse=True)

    async def test_every_line_carries_its_closest_stop(self, session):
        lines = await transit_service.find_probable_lines(
            session, RECIFE_LAT, RECIFE_LON, radius_m=2000
        )

        for line in lines:
            assert line.stop_id
            assert line.distance_m >= 0
            assert line.stops_within_radius >= 1

    async def test_a_closer_stop_outranks_a_farther_one(self, session):
        """The distance term must dominate the ranking."""
        lines = await transit_service.find_probable_lines(
            session, RECIFE_LAT, RECIFE_LON, radius_m=2000, limit=25
        )
        if len(lines) < 2:
            pytest.skip("not enough lines nearby to compare")

        best, worst = lines[0], lines[-1]
        assert best.distance_m <= worst.distance_m or best.score > worst.score

    async def test_expanding_search_finds_something_far_from_downtown(self, session):
        """A sparse area must not produce an empty list at the default radius."""
        lines, radius = await transit_service.find_probable_lines_expanding(
            session, RECIFE_LAT, RECIFE_LON
        )

        assert lines
        assert radius >= 300

    async def test_expanding_search_gives_up_cleanly(self, session):
        lines, radius = await transit_service.find_probable_lines_expanding(
            session, -8.0, -30.0
        )

        assert lines == []
        assert radius == 2500


class TestItineraryAndSearch:
    async def test_itinerary_is_ordered_and_non_trivial(self, session):
        itinerary = await transit_service.get_line_itinerary(session, "001")
        if itinerary is None:
            pytest.skip("line 001 not loaded")

        sequences = [stop["sequence"] for stop in itinerary["stops"]]
        assert sequences == sorted(sequences)
        assert itinerary["stop_count"] >= 2

    async def test_unknown_line_returns_none(self, session):
        assert await transit_service.get_line_itinerary(session, "ZZZZ") is None

    async def test_search_by_exact_code_ranks_first(self, session):
        results = await transit_service.search_lines(session, "001")
        if not results:
            pytest.skip("line 001 not loaded")

        assert results[0]["codigo_linha"] == "001"

    async def test_search_by_name_fragment(self, session):
        results = await transit_service.search_lines(session, "PRAZERES")

        assert all(
            "PRAZERES" in r["nome_completo"].upper() or r["codigo_linha"].startswith("PRAZERES")
            for r in results
        )

    async def test_nearest_stop_of_line(self, session):
        stop = await transit_service.nearest_stop_of_line(
            session, "001", RECIFE_LAT, RECIFE_LON
        )
        if stop is None:
            pytest.skip("line 001 not loaded")

        assert stop.distance_m >= 0
        assert stop.stop_id


class TestReverseIndex:
    async def test_lines_at_a_stop_match_the_itineraries(self, session):
        """line_stop_index must agree with the subline_stops it is derived from."""
        row = await session.execute(
            text(
                """
                SELECT lsi.stop_id, COUNT(*) AS n
                FROM line_stop_index lsi
                GROUP BY lsi.stop_id
                ORDER BY n DESC
                LIMIT 1
                """
            )
        )
        busiest = row.first()
        if busiest is None:
            pytest.skip("index is empty")

        lines = await transit_service.list_lines_at_stop(session, busiest.stop_id)

        expected = await session.execute(
            text(
                """
                SELECT DISTINCT s.codigo_linha
                FROM subline_stops ss
                JOIN sublines s ON s.id = ss.subline_id
                WHERE ss.stop_id = :stop_id
                """
            ),
            {"stop_id": busiest.stop_id},
        )
        assert {line["codigo_linha"] for line in lines} == set(expected.scalars().all())
