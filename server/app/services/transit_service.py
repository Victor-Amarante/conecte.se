"""Spatial and catalogue queries over the transit network loaded by the ETL.

All proximity work runs on ``stops.geom::geography`` so distances come back in
real metres, matching the ``ix_stops_geog_gist`` functional index created in
migration 0001.
"""

from dataclasses import dataclass

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

DEFAULT_RADIUS_M = 500
MAX_RADIUS_M = 5000


@dataclass(frozen=True)
class NearbyStop:
    stop_id: int
    codigo: str
    nome: str | None
    referencia: str | None
    is_terminal: bool
    latitude: float
    longitude: float
    distance_m: float

    def as_dict(self) -> dict:
        return {
            "stop_id": self.stop_id,
            "codigo": self.codigo,
            "nome": self.nome or self.codigo,
            "referencia": self.referencia,
            "is_terminal": self.is_terminal,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "distance_m": round(self.distance_m),
        }


@dataclass(frozen=True)
class ProbableLine:
    codigo_linha: str
    nome: str
    stop_id: int
    stop_codigo: str
    stop_nome: str | None
    stop_referencia: str | None
    distance_m: float
    stops_within_radius: int
    serves_terminal: bool
    score: float

    def as_dict(self) -> dict:
        return {
            "codigo_linha": self.codigo_linha,
            "nome": self.nome,
            "parada": {
                "stop_id": self.stop_id,
                "codigo": self.stop_codigo,
                "nome": self.stop_nome or self.stop_codigo,
                # Most ordinary stops are named by their numeric code, so the
                # reference ("EM FRENTE AO Nº749") is what a rider can act on.
                "referencia": self.stop_referencia,
                "distance_m": round(self.distance_m),
            },
            "stops_within_radius": self.stops_within_radius,
            "serves_terminal": self.serves_terminal,
            "score": round(self.score, 4),
        }


def _clamp_radius(radius_m: int) -> int:
    return max(50, min(int(radius_m), MAX_RADIUS_M))


class TransitService:
    """Read-only queries over the transit tables. Stateless; safe to share."""

    async def find_nearby_stops(
        self,
        session: AsyncSession,
        latitude: float,
        longitude: float,
        radius_m: int = DEFAULT_RADIUS_M,
        limit: int = 10,
    ) -> list[NearbyStop]:
        radius_m = _clamp_radius(radius_m)
        result = await session.execute(
            text(
                """
                SELECT
                    s.id, s.codigo, s.nome, s.referencia, s.is_terminal,
                    s.latitude, s.longitude,
                    ST_Distance(
                        s.geom::geography,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                    ) AS distance_m
                FROM stops s
                WHERE ST_DWithin(
                    s.geom::geography,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius
                )
                ORDER BY distance_m
                LIMIT :limit
                """
            ),
            {"lat": latitude, "lon": longitude, "radius": radius_m, "limit": limit},
        )
        return [
            NearbyStop(
                stop_id=row.id,
                codigo=row.codigo,
                nome=row.nome,
                referencia=row.referencia,
                is_terminal=row.is_terminal,
                latitude=row.latitude,
                longitude=row.longitude,
                distance_m=row.distance_m,
            )
            for row in result
        ]

    async def find_probable_lines(
        self,
        session: AsyncSession,
        latitude: float,
        longitude: float,
        radius_m: int = DEFAULT_RADIUS_M,
        limit: int = 8,
    ) -> list[ProbableLine]:
        """Rank the lines a user standing at (lat, lon) is most likely to want.

        Score combines three signals:

        * distance to the line's nearest stop — dominant, with a 200 m decay so
          a stop across the street clearly beats one three blocks away;
        * how many of the line's stops fall inside the radius, which separates
          a line that genuinely runs along this street from one that merely
          clips the corner;
        * whether one of those stops is a terminal, since terminals are both
          landmarks and high-frequency boarding points.
        """
        radius_m = _clamp_radius(radius_m)
        result = await session.execute(
            text(
                """
                WITH origin AS (
                    SELECT ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography AS g
                ),
                near AS (
                    SELECT
                        s.id, s.codigo, s.nome, s.referencia, s.is_terminal,
                        ST_Distance(s.geom::geography, origin.g) AS distance_m
                    FROM stops s, origin
                    WHERE ST_DWithin(s.geom::geography, origin.g, :radius)
                ),
                per_line AS (
                    SELECT
                        lsi.codigo_linha,
                        COUNT(*) AS stops_within_radius,
                        BOOL_OR(near.is_terminal) AS serves_terminal,
                        MIN(near.distance_m) AS distance_m
                    FROM near
                    JOIN line_stop_index lsi ON lsi.stop_id = near.id
                    GROUP BY lsi.codigo_linha
                ),
                closest AS (
                    SELECT DISTINCT ON (lsi.codigo_linha)
                        lsi.codigo_linha, near.id, near.codigo, near.nome,
                        near.referencia, near.distance_m
                    FROM near
                    JOIN line_stop_index lsi ON lsi.stop_id = near.id
                    ORDER BY lsi.codigo_linha, near.distance_m
                )
                SELECT
                    bl.codigo_linha,
                    bl.nome,
                    closest.id           AS stop_id,
                    closest.codigo       AS stop_codigo,
                    closest.nome         AS stop_nome,
                    closest.referencia   AS stop_referencia,
                    per_line.distance_m,
                    per_line.stops_within_radius,
                    per_line.serves_terminal,
                    (
                        (200.0 / (200.0 + per_line.distance_m))
                        + 0.15 * LEAST(per_line.stops_within_radius, 4) / 4.0
                        + CASE WHEN per_line.serves_terminal THEN 0.10 ELSE 0 END
                    ) AS score
                FROM per_line
                JOIN closest ON closest.codigo_linha = per_line.codigo_linha
                JOIN bus_lines bl ON bl.codigo_linha = per_line.codigo_linha
                WHERE bl.ativo
                ORDER BY score DESC, per_line.distance_m ASC
                LIMIT :limit
                """
            ),
            {"lat": latitude, "lon": longitude, "radius": radius_m, "limit": limit},
        )
        lines = [
            ProbableLine(
                codigo_linha=row.codigo_linha,
                nome=row.nome,
                stop_id=row.stop_id,
                stop_codigo=row.stop_codigo,
                stop_nome=row.stop_nome,
                stop_referencia=row.stop_referencia,
                distance_m=row.distance_m,
                stops_within_radius=row.stops_within_radius,
                serves_terminal=row.serves_terminal,
                score=float(row.score),
            )
            for row in result
        ]
        logger.info(
            f"find_probable_lines({latitude:.5f}, {longitude:.5f}, r={radius_m}m) "
            f"-> {len(lines)} lines"
        )
        return lines

    async def find_probable_lines_expanding(
        self,
        session: AsyncSession,
        latitude: float,
        longitude: float,
        limit: int = 8,
        radii: tuple[int, ...] = (300, 600, 1200, 2500),
    ) -> tuple[list[ProbableLine], int]:
        """Widen the search until something turns up.

        Users in low-density areas would otherwise get an empty list at the
        default radius. Returns the results and the radius that produced them.
        """
        for radius in radii:
            lines = await self.find_probable_lines(
                session, latitude, longitude, radius_m=radius, limit=limit
            )
            if lines:
                return lines, radius
        return [], radii[-1]

    async def list_lines_at_stop(
        self, session: AsyncSession, stop_id: int
    ) -> list[dict]:
        result = await session.execute(
            text(
                """
                SELECT bl.codigo_linha, bl.nome
                FROM line_stop_index lsi
                JOIN bus_lines bl ON bl.codigo_linha = lsi.codigo_linha
                WHERE lsi.stop_id = :stop_id AND bl.ativo
                ORDER BY bl.codigo_linha
                """
            ),
            {"stop_id": stop_id},
        )
        return [{"codigo_linha": r.codigo_linha, "nome": r.nome} for r in result]

    async def get_line(self, session: AsyncSession, codigo_linha: str) -> dict | None:
        result = await session.execute(
            text(
                """
                SELECT bl.codigo_linha, bl.nome, bl.nome_completo,
                       COUNT(sl.id) AS subline_count
                FROM bus_lines bl
                LEFT JOIN sublines sl ON sl.codigo_linha = bl.codigo_linha
                WHERE bl.codigo_linha = :codigo
                GROUP BY bl.codigo_linha, bl.nome, bl.nome_completo
                """
            ),
            {"codigo": codigo_linha},
        )
        row = result.first()
        if row is None:
            return None
        return {
            "codigo_linha": row.codigo_linha,
            "nome": row.nome,
            "nome_completo": row.nome_completo,
            "subline_count": row.subline_count,
        }

    async def get_line_itinerary(
        self,
        session: AsyncSession,
        codigo_linha: str,
        subline_label: str | None = "PRI",
    ) -> dict | None:
        """The ordered stop list of a line's subline (the main one by default)."""
        subline = await session.execute(
            text(
                """
                SELECT id, label, descricao
                FROM sublines
                WHERE codigo_linha = :codigo
                  -- The cast is required: asyncpg cannot infer the type of a
                  -- bare parameter used only in an IS NULL test.
                  AND (CAST(:label AS text) IS NULL OR label = CAST(:label AS text))
                ORDER BY (label = 'PRI') DESC, id
                LIMIT 1
                """
            ),
            {"codigo": codigo_linha, "label": subline_label},
        )
        subline_row = subline.first()
        if subline_row is None:
            # Asked-for variant does not exist; fall back to any subline.
            subline = await session.execute(
                text(
                    "SELECT id, label, descricao FROM sublines "
                    "WHERE codigo_linha = :codigo ORDER BY id LIMIT 1"
                ),
                {"codigo": codigo_linha},
            )
            subline_row = subline.first()
        if subline_row is None:
            return None

        result = await session.execute(
            text(
                """
                SELECT s.id, s.codigo, s.nome, s.is_terminal,
                       s.latitude, s.longitude, ss.sequence
                FROM subline_stops ss
                JOIN stops s ON s.id = ss.stop_id
                WHERE ss.subline_id = :subline_id
                ORDER BY ss.sequence
                """
            ),
            {"subline_id": subline_row.id},
        )
        stops = [
            {
                "stop_id": r.id,
                "codigo": r.codigo,
                "nome": r.nome or r.codigo,
                "is_terminal": r.is_terminal,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "sequence": r.sequence,
            }
            for r in result
        ]
        return {
            "codigo_linha": codigo_linha,
            "subline_id": subline_row.id,
            "subline_label": subline_row.label,
            "subline_descricao": subline_row.descricao,
            "stop_count": len(stops),
            "stops": stops,
        }

    async def search_lines(
        self, session: AsyncSession, termo: str, limit: int = 10
    ) -> list[dict]:
        """Find lines by code or name. Exact code matches rank first."""
        result = await session.execute(
            text(
                """
                SELECT codigo_linha, nome, nome_completo
                FROM bus_lines
                WHERE ativo
                  AND (codigo_linha ILIKE :prefix OR nome_completo ILIKE :contains)
                ORDER BY
                    (codigo_linha = :exact) DESC,
                    (codigo_linha ILIKE :prefix) DESC,
                    codigo_linha
                LIMIT :limit
                """
            ),
            {
                "exact": termo,
                "prefix": f"{termo}%",
                "contains": f"%{termo}%",
                "limit": limit,
            },
        )
        return [
            {
                "codigo_linha": r.codigo_linha,
                "nome": r.nome,
                "nome_completo": r.nome_completo,
            }
            for r in result
        ]

    async def downstream_stop_of_line(
        self,
        session: AsyncSession,
        codigo_linha: str,
        stop_id: int,
        stops_ahead: int = 12,
    ) -> NearbyStop | None:
        """Uma parada adiante de ``stop_id`` que seja *exclusiva* desta linha.

        Serve de destino ao pedir uma rota ao Google. E aqui está a sutileza que
        faz a coisa funcionar: a Routes API devolve a linha **mais rápida** entre
        dois pontos, não a que pedimos. Escolher qualquer parada à frente não
        basta — em corredores movimentados o Google responde com uma das dezenas
        de linhas concorrentes e a linha do usuário nunca aparece.

        Por isso preferimos a parada adiante servida pelo **menor número de
        outras linhas**: quanto mais exclusiva, menos alternativa o roteador tem
        além de usar a linha que nos interessa.
        """
        result = await session.execute(
            text(
                """
                WITH alvo AS (
                    SELECT ss.subline_id, ss.sequence
                    FROM subline_stops ss
                    JOIN sublines sl ON sl.id = ss.subline_id
                    WHERE sl.codigo_linha = :codigo AND ss.stop_id = :stop_id
                    ORDER BY (sl.label = 'PRI') DESC, sl.id
                    LIMIT 1
                ),
                candidatas AS (
                    SELECT s.id, s.codigo, s.nome, s.referencia, s.is_terminal,
                           s.latitude, s.longitude,
                           ss.sequence - alvo.sequence AS adiante,
                           (SELECT COUNT(*) FROM line_stop_index lsi
                            WHERE lsi.stop_id = s.id) AS concorrentes
                    FROM subline_stops ss
                    JOIN alvo ON alvo.subline_id = ss.subline_id
                    JOIN stops s ON s.id = ss.stop_id
                    -- Perto demais e o Google sugere caminhar; a margem
                    -- garante que a viagem de ônibus valha a pena.
                    WHERE ss.sequence >= alvo.sequence + 4
                )
                SELECT id, codigo, nome, referencia, is_terminal,
                       latitude, longitude
                FROM candidatas
                ORDER BY concorrentes ASC, ABS(adiante - :ahead) ASC
                LIMIT 1
                """
            ),
            {"codigo": codigo_linha, "stop_id": stop_id, "ahead": stops_ahead},
        )
        row = result.first()
        if row is None:
            return None
        return NearbyStop(
            stop_id=row.id,
            codigo=row.codigo,
            nome=row.nome,
            referencia=row.referencia,
            is_terminal=row.is_terminal,
            latitude=row.latitude,
            longitude=row.longitude,
            distance_m=0.0,
        )

    async def nearest_stop_of_line(
        self,
        session: AsyncSession,
        codigo_linha: str,
        latitude: float,
        longitude: float,
    ) -> NearbyStop | None:
        """The stop of a given line closest to a point — the user's boarding point."""
        result = await session.execute(
            text(
                """
                SELECT s.id, s.codigo, s.nome, s.referencia, s.is_terminal,
                       s.latitude, s.longitude,
                       ST_Distance(
                           s.geom::geography,
                           ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                       ) AS distance_m
                FROM line_stop_index lsi
                JOIN stops s ON s.id = lsi.stop_id
                WHERE lsi.codigo_linha = :codigo
                ORDER BY distance_m
                LIMIT 1
                """
            ),
            {"codigo": codigo_linha, "lat": latitude, "lon": longitude},
        )
        row = result.first()
        if row is None:
            return None
        return NearbyStop(
            stop_id=row.id,
            codigo=row.codigo,
            nome=row.nome,
            referencia=row.referencia,
            is_terminal=row.is_terminal,
            latitude=row.latitude,
            longitude=row.longitude,
            distance_m=row.distance_m,
        )


transit_service = TransitService()
