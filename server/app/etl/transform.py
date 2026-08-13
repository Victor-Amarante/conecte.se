"""Normalisation of raw RUMO payloads into database-ready records.

The single most important job here is the coordinate conversion. RUMO serves
UTM zone 25S metres and converts them in the browser with proj4 using
``+proj=utm +zone=25 +south +ellps=WGS84 +datum=WGS84 +units=m +no_defs``,
which is EPSG:32725. We do the same conversion server-side so that everything
downstream is plain WGS84 (EPSG:4326).
"""

import re
from dataclasses import dataclass, field
from functools import lru_cache

from loguru import logger
from pyproj import Transformer

UTM_25S = "EPSG:32725"
WGS84 = "EPSG:4326"

# Major boarding points — terminals and BRT stations. We use this to rank
# lines, so the question is "is this a significant place to board?", not
# "which icon does RUMO draw?".
#
# RUMO's own paradas.js uses {5, 26, 27} for its terminal icon, which is too
# narrow here and includes a class that no stop actually has. Measured over the
# full 7136-stop inventory:
#   26 (210) and 27 (38)  — all named "TI ..."          -> terminals
#   4  (110)              — 103 named "Terminal ..."    -> terminals
#   28 (14)               — all named "TP ..."          -> passenger terminals
#   11 (62)               — all named "Estação ..."     -> BRT stations
#   1, 2, 3, 8            — ordinary stops, numeric codes only
TERMINAL_STOP_CLASSES = {4, 5, 11, 26, 27, 28}

# Class 4 is 94% terminals, not 100%, so the class alone would mislabel a few
# stops either way. The name is the tiebreaker RUMO gives us for free.
_TERMINAL_NAME_RE = re.compile(r"^\s*(TI\b|TP\b|Terminal\b|Esta[çc][ãa]o\b)", re.I)


def looks_like_terminal(clase: int, nome: str | None) -> bool:
    if nome and _TERMINAL_NAME_RE.match(nome):
        return True
    if nome and nome.strip().isdigit():
        # A bare numeric code is an ordinary stop, whatever its class says.
        return False
    return clase in TERMINAL_STOP_CLASSES

# Sanity envelope for the Recife metropolitan region. Anything outside is a
# conversion or upstream error and gets dropped rather than poisoning the index.
RMR_BBOX = (-9.0, -7.0, -36.0, -34.0)  # min_lat, max_lat, min_lon, max_lon


@lru_cache(maxsize=1)
def _transformer() -> Transformer:
    return Transformer.from_crs(UTM_25S, WGS84, always_xy=True)


def utm_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert UTM zone 25S metres to ``(latitude, longitude)`` degrees."""
    lon, lat = _transformer().transform(easting, northing)
    return lat, lon


def is_within_rmr(latitude: float, longitude: float) -> bool:
    min_lat, max_lat, min_lon, max_lon = RMR_BBOX
    return min_lat <= latitude <= max_lat and min_lon <= longitude <= max_lon


@dataclass
class StopRecord:
    id: int
    nodo: int
    codigo: str
    nome: str | None
    referencia: str | None
    clase: int
    is_terminal: bool
    latitude: float
    longitude: float


@dataclass
class SublineStopRecord:
    subline_id: int
    sequence: int
    stop_id: int
    orden: int | None
    posicion: int | None


@dataclass
class ShapeRecord:
    subline_id: int
    idrota: int | None
    idseccion: int | None
    idramal: int | None
    ordem: int
    points: list[tuple[float, float]] = field(default_factory=list)  # (lon, lat)


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text or None


def transform_stops(raw_stops: list[dict]) -> tuple[list[StopRecord], int]:
    """Convert the ``json_mapa_paradas`` inventory. Returns (records, dropped)."""
    records: list[StopRecord] = []
    dropped = 0

    for row in raw_stops:
        try:
            latitude, longitude = utm_to_wgs84(float(row["posX"]), float(row["posY"]))
        except (KeyError, TypeError, ValueError):
            dropped += 1
            continue

        if not is_within_rmr(latitude, longitude):
            logger.warning(
                f"Stop {row.get('nodo')} outside the RMR envelope "
                f"({latitude:.5f}, {longitude:.5f}) — skipped"
            )
            dropped += 1
            continue

        clase = int(row.get("clase") or 0)
        codigo = _clean(row.get("nombre")) or str(row["nodo"])
        records.append(
            StopRecord(
                id=int(row["id"]),
                nodo=int(row["nodo"]),
                codigo=codigo,
                nome=None,
                referencia=None,
                clase=clase,
                is_terminal=looks_like_terminal(clase, codigo),
                latitude=latitude,
                longitude=longitude,
            )
        )

    return records, dropped


def enrich_stops_from_itinerary(
    stops_by_nodo: dict[int, StopRecord], raw_itinerary: list[dict]
) -> None:
    """Fill in ``nome``/``referencia``, which only the itinerary endpoint carries.

    ``json_mapa_paradas`` gives geometry but no human-readable label; the
    per-subline itinerary gives both. Mutates ``stops_by_nodo`` in place.
    """
    for row in raw_itinerary:
        nodo = row.get("nodo")
        stop = stops_by_nodo.get(nodo)
        if stop is None:
            continue
        nome = _clean(row.get("nombre"))
        # Prefer a descriptive name ("Terminal de Ponte dos Carvalhos - 190223")
        # over the bare numeric code the inventory already has.
        if nome and (stop.nome is None or len(nome) > len(stop.nome)):
            stop.nome = nome
        referencia = _clean(row.get("referencia"))
        if referencia and not stop.referencia:
            stop.referencia = referencia


def transform_subline_stops(
    subline_id: int, raw_itinerary: list[dict], nodo_to_stop_id: dict[int, int]
) -> tuple[list[SublineStopRecord], int]:
    """Convert one subline's itinerary. Returns (records, orphan_count).

    ``nodo`` is the join key to the stop inventory. Itinerary entries whose
    nodo is absent from the inventory are logged and skipped — never fatal.
    """
    records: list[SublineStopRecord] = []
    orphans = 0
    seen_stop_ids: set[int] = set()

    for row in raw_itinerary:
        nodo = row.get("nodo")
        stop_id = nodo_to_stop_id.get(nodo)
        if stop_id is None:
            orphans += 1
            continue
        # A circular route can legitimately revisit a stop; keep the first hit
        # so (subline_id, stop_id) stays usable as a reverse-index key.
        if stop_id in seen_stop_ids:
            continue
        seen_stop_ids.add(stop_id)

        records.append(
            SublineStopRecord(
                subline_id=subline_id,
                sequence=len(records),
                stop_id=stop_id,
                orden=_as_int(row.get("orden")),
                posicion=_as_int(row.get("posicion")),
            )
        )

    return records, orphans


def _as_int(value: object) -> int | None:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def transform_shape(subline_id: int, raw_shape: list[dict]) -> list[ShapeRecord]:
    """Group the flat shape point list into ordered LineString segments.

    Points arrive flat but carry ``idrota``/``idseccion``/``idRamal`` plus
    ordering columns; each (rota, seccion, ramal) triple is one polyline.
    """
    grouped: dict[tuple, ShapeRecord] = {}

    for row in raw_shape:
        try:
            easting = float(str(row["xlon"]).strip())
            northing = float(str(row["ylat"]).strip())
        except (KeyError, TypeError, ValueError):
            continue

        latitude, longitude = utm_to_wgs84(easting, northing)
        if not is_within_rmr(latitude, longitude):
            continue

        key = (row.get("idrota"), row.get("idseccion"), row.get("idRamal"))
        segment = grouped.get(key)
        if segment is None:
            segment = ShapeRecord(
                subline_id=subline_id,
                idrota=_as_int(row.get("idrota")),
                idseccion=_as_int(row.get("idseccion")),
                idramal=_as_int(row.get("idRamal")),
                ordem=_as_int(row.get("ordemSeccionesRuta")) or 0,
            )
            grouped[key] = segment
        segment.points.append((longitude, latitude))

    # A LineString needs at least two distinct points.
    segments = [s for s in grouped.values() if len(s.points) >= 2]
    segments.sort(key=lambda s: (s.ordem, s.idseccion or 0))
    return segments


def to_wkt_point(latitude: float, longitude: float) -> str:
    return f"SRID=4326;POINT({longitude} {latitude})"


def to_wkt_linestring(points: list[tuple[float, float]]) -> str:
    body = ", ".join(f"{lon} {lat}" for lon, lat in points)
    return f"SRID=4326;LINESTRING({body})"
