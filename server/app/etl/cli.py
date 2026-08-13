"""Command line entrypoint for the RUMO ETL.

    uv run python -m app.etl.cli sync
    uv run python -m app.etl.cli sync --lines 001,011,191 --skip-shapes
    uv run python -m app.etl.cli validate --stop 190126
"""

import argparse
import asyncio
import sys

from loguru import logger

from app.db.session import dispose_engine


async def _cmd_sync(args: argparse.Namespace) -> int:
    from app.etl.pipeline import run_sync

    only_lines = (
        [code.strip() for code in args.lines.split(",") if code.strip()]
        if args.lines
        else None
    )
    stats = await run_sync(
        only_lines=only_lines,
        skip_shapes=args.skip_shapes,
        save_raw=not args.no_raw,
        dry_run=args.dry_run,
    )
    print("\nSync stats:")
    for key, value in stats.as_dict().items():
        print(f"  {key:20} {value}")
    return 0


async def _cmd_reprocess(args: argparse.Namespace) -> int:
    from pathlib import Path

    from app.etl.pipeline import latest_snapshot, run_reprocess

    directory = Path(args.snapshot) if args.snapshot else latest_snapshot()
    if directory is None:
        print("No snapshot found under data/raw/ — run `sync` first.")
        return 1

    print(f"Reprocessing {directory}")
    stats = await run_reprocess(directory, skip_shapes=args.skip_shapes)
    print("\nReprocess stats:")
    for key, value in stats.as_dict().items():
        print(f"  {key:20} {value}")
    return 0


async def _cmd_validate(args: argparse.Namespace) -> int:
    """Cross-check the derived index against RUMO's own stop->lines endpoint."""
    from sqlalchemy import select

    from app.db.models import LineStopIndex, Stop
    from app.db.session import SessionLocal
    from app.etl.rumo_client import RumoClient

    async with RumoClient() as client:
        upstream = await client.fetch_stop_lines(args.stop)
    expected = sorted({row["codigoLinha"] for row in upstream})

    async with SessionLocal() as session:
        result = await session.execute(
            select(LineStopIndex.codigo_linha)
            .join(Stop, Stop.id == LineStopIndex.stop_id)
            .where(Stop.codigo == args.stop)
        )
        actual = sorted(set(result.scalars().all()))

    print(f"stop {args.stop}")
    print(f"  RUMO says : {expected}")
    print(f"  we have   : {actual}")

    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    if missing:
        print(f"  MISSING   : {missing}")
    if extra:
        print(f"  EXTRA     : {extra}")
    if not missing and not extra:
        print("  match ✓")
        return 0
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="app.etl.cli", description="RUMO ETL")
    sub = parser.add_subparsers(dest="command", required=True)

    sync = sub.add_parser("sync", help="Synchronise the transit network from RUMO")
    sync.add_argument("--lines", help="Comma-separated line codes (default: all)")
    sync.add_argument(
        "--skip-shapes",
        action="store_true",
        help="Skip route polylines — much faster, stops and itineraries only",
    )
    sync.add_argument(
        "--no-raw", action="store_true", help="Do not write raw payload snapshots"
    )
    sync.add_argument(
        "--dry-run", action="store_true", help="Roll back instead of committing"
    )
    sync.set_defaults(func=_cmd_sync)

    reprocess = sub.add_parser(
        "reprocess",
        help="Re-run transform and load from a saved snapshot, without touching RUMO",
    )
    reprocess.add_argument(
        "--snapshot", help="Snapshot directory (default: the most recent one)"
    )
    reprocess.add_argument("--skip-shapes", action="store_true")
    reprocess.set_defaults(func=_cmd_reprocess)

    validate = sub.add_parser(
        "validate", help="Compare our line_stop_index against RUMO for one stop"
    )
    validate.add_argument("--stop", required=True, help="Stop code, e.g. 190126")
    validate.set_defaults(func=_cmd_validate)

    return parser


async def _main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return await args.func(args)
    finally:
        await dispose_engine()


def main() -> None:
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    raise SystemExit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
