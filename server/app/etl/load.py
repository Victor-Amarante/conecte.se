"""Idempotent loading of transformed RUMO records into Postgres/PostGIS.

Every write is an upsert, so a sync never deletes good data: a failed or
partial run leaves the previous snapshot intact and the next run repairs it.
"""

from typing import Iterable, Sequence

from loguru import logger
from sqlalchemy import delete, func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    BusLine,
    LineStopIndex,
    Stop,
    Subline,
    SublineShape,
    SublineStop,
)
from app.etl.parsers import ParsedLine, ParsedSubline
from app.etl.transform import (
    ShapeRecord,
    StopRecord,
    SublineStopRecord,
    to_wkt_linestring,
    to_wkt_point,
)

CHUNK_SIZE = 1000


def _chunks(items: Sequence, size: int = CHUNK_SIZE) -> Iterable[Sequence]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


async def upsert_lines(session: AsyncSession, lines: Sequence[ParsedLine]) -> int:
    if not lines:
        return 0
    rows = [
        {
            "codigo_linha": line.codigo_linha,
            "nome": line.nome,
            "nome_completo": line.nome_completo,
            "ativo": True,
        }
        for line in lines
    ]
    for chunk in _chunks(rows):
        stmt = insert(BusLine).values(list(chunk))
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[BusLine.codigo_linha],
                set_={
                    "nome": stmt.excluded.nome,
                    "nome_completo": stmt.excluded.nome_completo,
                    "ativo": stmt.excluded.ativo,
                    "updated_at": func.now(),
                },
            )
        )
    logger.info(f"Upserted {len(rows)} bus lines")
    return len(rows)


async def upsert_sublines(
    session: AsyncSession, sublines: Sequence[tuple[str, ParsedSubline]]
) -> int:
    if not sublines:
        return 0
    rows = [
        {
            "id": subline.id,
            "codigo_linha": codigo_linha,
            "label": subline.label,
            "descricao": subline.descricao,
        }
        for codigo_linha, subline in sublines
    ]
    for chunk in _chunks(rows):
        stmt = insert(Subline).values(list(chunk))
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Subline.id],
                set_={
                    "codigo_linha": stmt.excluded.codigo_linha,
                    "label": stmt.excluded.label,
                    "descricao": stmt.excluded.descricao,
                    "updated_at": func.now(),
                },
            )
        )
    logger.info(f"Upserted {len(rows)} sublines")
    return len(rows)


async def upsert_stops(session: AsyncSession, stops: Sequence[StopRecord]) -> int:
    if not stops:
        return 0
    rows = [
        {
            "id": stop.id,
            "nodo": stop.nodo,
            "codigo": stop.codigo,
            "nome": stop.nome,
            "referencia": stop.referencia,
            "clase": stop.clase,
            "is_terminal": stop.is_terminal,
            "latitude": stop.latitude,
            "longitude": stop.longitude,
            "geom": to_wkt_point(stop.latitude, stop.longitude),
        }
        for stop in stops
    ]
    for chunk in _chunks(rows):
        stmt = insert(Stop).values(list(chunk))
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[Stop.id],
                set_={
                    "nodo": stmt.excluded.nodo,
                    "codigo": stmt.excluded.codigo,
                    # Names/references only exist in itinerary payloads, so keep
                    # the value we already have when a run does not supply one.
                    "nome": func.coalesce(stmt.excluded.nome, Stop.nome),
                    "referencia": func.coalesce(
                        stmt.excluded.referencia, Stop.referencia
                    ),
                    "clase": stmt.excluded.clase,
                    "is_terminal": stmt.excluded.is_terminal,
                    "latitude": stmt.excluded.latitude,
                    "longitude": stmt.excluded.longitude,
                    "geom": stmt.excluded.geom,
                    "updated_at": func.now(),
                },
            )
        )
    logger.info(f"Upserted {len(rows)} stops")
    return len(rows)


async def replace_subline_stops(
    session: AsyncSession, subline_id: int, records: Sequence[SublineStopRecord]
) -> int:
    """Rewrite one subline's itinerary atomically.

    Replace rather than upsert: stops can be removed from a route, and a stale
    tail would silently keep a line associated with a stop it no longer serves.
    """
    await session.execute(
        delete(SublineStop).where(SublineStop.subline_id == subline_id)
    )
    if not records:
        return 0
    rows = [
        {
            "subline_id": r.subline_id,
            "sequence": r.sequence,
            "stop_id": r.stop_id,
            "orden": r.orden,
            "posicion": r.posicion,
        }
        for r in records
    ]
    for chunk in _chunks(rows):
        await session.execute(insert(SublineStop).values(list(chunk)))
    return len(rows)


async def replace_subline_shape(
    session: AsyncSession, subline_id: int, segments: Sequence[ShapeRecord]
) -> int:
    await session.execute(
        delete(SublineShape).where(SublineShape.subline_id == subline_id)
    )
    if not segments:
        return 0
    rows = [
        {
            "subline_id": seg.subline_id,
            "idrota": seg.idrota,
            "idseccion": seg.idseccion,
            "idramal": seg.idramal,
            "ordem": seg.ordem,
            "geom": to_wkt_linestring(seg.points),
        }
        for seg in segments
    ]
    for chunk in _chunks(rows, 200):
        await session.execute(insert(SublineShape).values(list(chunk)))
    return len(rows)


async def rebuild_line_stop_index(session: AsyncSession) -> int:
    """Materialise line -> stop from the subline itineraries.

    Rebuilt wholesale inside the caller's transaction so readers never observe
    a half-built index.
    """
    await session.execute(delete(LineStopIndex))
    result = await session.execute(
        text(
            """
            INSERT INTO line_stop_index (codigo_linha, stop_id)
            SELECT DISTINCT s.codigo_linha, ss.stop_id
            FROM subline_stops ss
            JOIN sublines s ON s.id = ss.subline_id
            """
        )
    )
    count = result.rowcount or 0
    logger.info(f"Rebuilt line_stop_index with {count} rows")
    return count


async def analyze_tables(session: AsyncSession) -> None:
    """Refresh planner statistics so the spatial index actually gets used."""
    for table in ("stops", "line_stop_index", "subline_stops", "bus_lines"):
        await session.execute(text(f"ANALYZE {table}"))
