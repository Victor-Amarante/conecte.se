"""Orchestration of a full RUMO synchronisation.

Shape of a run:

1. fetch the line catalogue (1 request) and the stop inventory (1 request);
2. fetch each line's sublines (~390 requests, concurrency-limited);
3. fetch each subline's itinerary and, optionally, its shape (~600 each);
4. transform, then load in dependency order inside one transaction per stage;
5. rebuild the derived ``line_stop_index``.

The raw payloads are written to ``data/raw/<timestamp>/`` before transforming
so a run can be reprocessed without hitting RUMO again.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from pathlib import Path

from app.core.config import DATA_DIR
from app.db.models import ETLRun
from app.db.session import SessionLocal
from app.etl.load import (
    analyze_tables,
    rebuild_line_stop_index,
    replace_subline_shape,
    replace_subline_stops,
    upsert_lines,
    upsert_stops,
    upsert_sublines,
)
from app.etl.parsers import ParsedLine, ParsedSubline
from app.etl.rumo_client import RumoClient
from app.etl.transform import (
    enrich_stops_from_itinerary,
    transform_shape,
    transform_stops,
    transform_subline_stops,
)


@dataclass
class SyncStats:
    lines: int = 0
    sublines: int = 0
    stops: int = 0
    stops_dropped: int = 0
    itinerary_rows: int = 0
    shape_segments: int = 0
    orphan_nodes: int = 0
    sublines_empty: list[int] = field(default_factory=list)
    line_stop_index: int = 0

    def as_dict(self) -> dict:
        return {
            "lines": self.lines,
            "sublines": self.sublines,
            "stops": self.stops,
            "stops_dropped": self.stops_dropped,
            "itinerary_rows": self.itinerary_rows,
            "shape_segments": self.shape_segments,
            "orphan_nodes": self.orphan_nodes,
            "sublines_empty": self.sublines_empty[:50],
            "line_stop_index": self.line_stop_index,
        }


class RumoSyncPipeline:
    def __init__(
        self,
        client: RumoClient,
        *,
        only_lines: list[str] | None = None,
        skip_shapes: bool = False,
        save_raw: bool = True,
    ) -> None:
        self.client = client
        self.only_lines = set(only_lines) if only_lines else None
        self.skip_shapes = skip_shapes
        self.save_raw = save_raw
        self.stats = SyncStats()
        self.raw_dir = DATA_DIR / "raw" / datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )

    # ------------------------------------------------------------------

    def _dump_raw(self, name: str, payload: object) -> None:
        if not self.save_raw:
            return
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        path = self.raw_dir / f"{name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    async def _gather_sublines(
        self, lines: list[ParsedLine]
    ) -> list[tuple[str, ParsedSubline]]:
        async def one(line: ParsedLine) -> list[tuple[str, ParsedSubline]]:
            try:
                sublines = await self.client.fetch_sublines(line.codigo_linha)
            except Exception as exc:
                logger.error(f"Failed to fetch sublines for {line.codigo_linha}: {exc}")
                return []
            if not sublines:
                logger.warning(f"Line {line.codigo_linha} has no sublines")
            return [(line.codigo_linha, s) for s in sublines]

        results = await asyncio.gather(*(one(line) for line in lines))
        flat = [pair for group in results for pair in group]
        self._dump_raw(
            "sublines",
            [
                {
                    "codigo_linha": codigo,
                    "id": s.id,
                    "label": s.label,
                    "descricao": s.descricao,
                }
                for codigo, s in flat
            ],
        )
        return flat

    async def _gather_itineraries(self, subline_ids: list[int]) -> dict[int, list[dict]]:
        async def one(subline_id: int) -> tuple[int, list[dict]]:
            try:
                return subline_id, await self.client.fetch_subline_stops(subline_id)
            except Exception as exc:
                logger.error(f"Failed to fetch itinerary for subline {subline_id}: {exc}")
                return subline_id, []

        results = await asyncio.gather(*(one(sid) for sid in subline_ids))
        payload = {sid: rows for sid, rows in results}
        self._dump_raw("itineraries", {str(k): v for k, v in payload.items()})
        return payload

    async def _gather_shapes(self, subline_ids: list[int]) -> dict[int, list[dict]]:
        async def one(subline_id: int) -> tuple[int, list[dict]]:
            try:
                return subline_id, await self.client.fetch_subline_shape(subline_id)
            except Exception as exc:
                logger.error(f"Failed to fetch shape for subline {subline_id}: {exc}")
                return subline_id, []

        results = await asyncio.gather(*(one(sid) for sid in subline_ids))
        payload = {sid: rows for sid, rows in results}
        self._dump_raw("shapes", {str(k): v for k, v in payload.items()})
        return payload

    # ------------------------------------------------------------------

    async def run(self, session: AsyncSession) -> SyncStats:
        logger.info("RUMO sync starting")

        lines = await self.client.fetch_lines()
        if self.only_lines:
            lines = [line for line in lines if line.codigo_linha in self.only_lines]
            logger.info(f"Restricted to {len(lines)} lines: {sorted(self.only_lines)}")
        self._dump_raw("lines", [line.__dict__ for line in lines])
        self.stats.lines = len(lines)

        raw_stops = await self.client.fetch_all_stops()
        self._dump_raw("stops", raw_stops)
        stops, dropped = transform_stops(raw_stops)
        self.stats.stops = len(stops)
        self.stats.stops_dropped = dropped

        subline_pairs = await self._gather_sublines(lines)
        self.stats.sublines = len(subline_pairs)
        subline_ids = [subline.id for _, subline in subline_pairs]

        itineraries = await self._gather_itineraries(subline_ids)

        # Itinerary payloads are the only source of stop names and references,
        # so enrich before the stops are written.
        stops_by_nodo = {stop.nodo: stop for stop in stops}
        for rows in itineraries.values():
            enrich_stops_from_itinerary(stops_by_nodo, rows)

        shapes: dict[int, list[dict]] = {}
        if not self.skip_shapes:
            shapes = await self._gather_shapes(subline_ids)

        await self._load(session, lines, stops, subline_pairs, itineraries, shapes)
        logger.info(f"RUMO sync finished: {self.stats.as_dict()}")
        return self.stats

    async def _load(
        self,
        session: AsyncSession,
        lines: list[ParsedLine],
        stops: list,
        subline_pairs: list[tuple[str, ParsedSubline]],
        itineraries: dict[int, list[dict]],
        shapes: dict[int, list[dict]],
    ) -> None:
        """Transform-and-load, in dependency order.

        Shared with the offline reprocessing path so a change to the transform
        rules can be applied to a saved snapshot without re-scraping RUMO.
        """
        await upsert_lines(session, lines)
        await upsert_stops(session, stops)
        await upsert_sublines(session, subline_pairs)
        await session.flush()

        nodo_to_stop_id = {stop.nodo: stop.id for stop in stops}
        for subline_id, rows in itineraries.items():
            records, orphans = transform_subline_stops(
                subline_id, rows, nodo_to_stop_id
            )
            self.stats.orphan_nodes += orphans
            if len(records) < 2:
                logger.warning(
                    f"Subline {subline_id} has {len(records)} usable stops — skipped"
                )
                self.stats.sublines_empty.append(subline_id)
                continue
            self.stats.itinerary_rows += await replace_subline_stops(
                session, subline_id, records
            )

        for subline_id, rows in shapes.items():
            segments = transform_shape(subline_id, rows)
            self.stats.shape_segments += await replace_subline_shape(
                session, subline_id, segments
            )

        self.stats.line_stop_index = await rebuild_line_stop_index(session)
        await analyze_tables(session)


class RumoReprocessPipeline(RumoSyncPipeline):
    """Re-run transform and load against a saved raw snapshot.

    RUMO is an unversioned third party and rate-limits aggressive clients, so
    every transform change must be applicable without hitting it again.
    """

    def __init__(self, snapshot_dir: Path, *, skip_shapes: bool = False) -> None:
        super().__init__(client=None, skip_shapes=skip_shapes, save_raw=False)
        self.snapshot_dir = snapshot_dir

    def _read(self, name: str):
        path = self.snapshot_dir / f"{name}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    async def run(self, session: AsyncSession) -> SyncStats:
        logger.info(f"Reprocessing snapshot {self.snapshot_dir}")

        raw_lines = self._read("lines")
        raw_stops = self._read("stops")
        raw_sublines = self._read("sublines")
        raw_itineraries = self._read("itineraries")
        if raw_lines is None or raw_stops is None or raw_sublines is None:
            raise FileNotFoundError(
                f"{self.snapshot_dir} is missing lines/stops/sublines snapshots"
            )

        lines = [ParsedLine(**row) for row in raw_lines]
        self.stats.lines = len(lines)

        stops, dropped = transform_stops(raw_stops)
        self.stats.stops = len(stops)
        self.stats.stops_dropped = dropped

        subline_pairs = [
            (
                row["codigo_linha"],
                ParsedSubline(
                    id=row["id"], label=row["label"], descricao=row["descricao"]
                ),
            )
            for row in raw_sublines
        ]
        self.stats.sublines = len(subline_pairs)

        itineraries = {int(k): v for k, v in (raw_itineraries or {}).items()}
        stops_by_nodo = {stop.nodo: stop for stop in stops}
        for rows in itineraries.values():
            enrich_stops_from_itinerary(stops_by_nodo, rows)

        shapes: dict[int, list[dict]] = {}
        if not self.skip_shapes:
            raw_shapes = self._read("shapes")
            if raw_shapes is None:
                logger.warning(
                    "Snapshot has no shapes; existing route geometry is left as is"
                )
            else:
                shapes = {int(k): v for k, v in raw_shapes.items()}

        await self._load(session, lines, stops, subline_pairs, itineraries, shapes)
        logger.info(f"Reprocess finished: {self.stats.as_dict()}")
        return self.stats


def latest_snapshot() -> Path | None:
    raw_root = DATA_DIR / "raw"
    if not raw_root.exists():
        return None
    snapshots = sorted(p for p in raw_root.iterdir() if p.is_dir())
    return snapshots[-1] if snapshots else None


async def run_reprocess(
    snapshot_dir: Path | None = None, *, skip_shapes: bool = False
) -> SyncStats:
    directory = snapshot_dir or latest_snapshot()
    if directory is None:
        raise FileNotFoundError("no raw snapshot found under data/raw/")

    pipeline = RumoReprocessPipeline(directory, skip_shapes=skip_shapes)
    async with SessionLocal() as session:
        stats = await pipeline.run(session)
        await session.commit()
    return stats


async def run_sync(
    *,
    only_lines: list[str] | None = None,
    skip_shapes: bool = False,
    save_raw: bool = True,
    dry_run: bool = False,
) -> SyncStats:
    """Run a full sync, recording the outcome in ``etl_runs``."""
    async with SessionLocal() as session:
        run = ETLRun(status="running")
        session.add(run)
        await session.commit()
        run_id = run.id

    stats = SyncStats()
    try:
        async with RumoClient() as client:
            pipeline = RumoSyncPipeline(
                client,
                only_lines=only_lines,
                skip_shapes=skip_shapes,
                save_raw=save_raw,
            )
            async with SessionLocal() as session:
                stats = await pipeline.run(session)
                if dry_run:
                    logger.warning("dry-run: rolling back")
                    await session.rollback()
                else:
                    await session.commit()
    except Exception as exc:
        logger.exception("RUMO sync failed")
        async with SessionLocal() as session:
            await session.execute(
                update(ETLRun)
                .where(ETLRun.id == run_id)
                .values(
                    status="failed",
                    finished_at=datetime.now(timezone.utc),
                    error=str(exc)[:4000],
                    stats=stats.as_dict(),
                )
            )
            await session.commit()
        raise

    async with SessionLocal() as session:
        await session.execute(
            update(ETLRun)
            .where(ETLRun.id == run_id)
            .values(
                status="dry-run" if dry_run else "success",
                finished_at=datetime.now(timezone.utc),
                stats=stats.as_dict(),
            )
        )
        await session.commit()

    return stats
