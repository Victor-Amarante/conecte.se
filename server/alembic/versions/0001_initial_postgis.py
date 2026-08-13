"""initial schema with PostGIS

Revision ID: 0001
Revises:
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "bus_lines",
        sa.Column("codigo_linha", sa.String(16), primary_key=True),
        sa.Column("nome", sa.String(255), nullable=False),
        sa.Column("nome_completo", sa.String(320), nullable=False),
        sa.Column("ativo", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_bus_lines_nome_trgm",
        "bus_lines",
        ["nome"],
        postgresql_using="gin",
        postgresql_ops={"nome": "gin_trgm_ops"},
    )

    op.create_table(
        "sublines",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("codigo_linha", sa.String(16), nullable=False),
        sa.Column("label", sa.String(16), nullable=True),
        sa.Column("descricao", sa.String(255), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["codigo_linha"], ["bus_lines.codigo_linha"], ondelete="CASCADE"
        ),
    )
    op.create_index("ix_sublines_codigo_linha", "sublines", ["codigo_linha"])

    op.create_table(
        "stops",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("nodo", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(64), nullable=False),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("referencia", sa.Text(), nullable=True),
        sa.Column("clase", sa.Integer(), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.Geometry(
                geometry_type="POINT", srid=4326, spatial_index=False
            ),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_stops_nodo", "stops", ["nodo"], unique=True)
    op.create_index("ix_stops_codigo", "stops", ["codigo"])
    # Proximity queries use ST_DWithin(geom::geography, ...); a plain geometry
    # GiST index would not be usable by that predicate, so index the cast.
    op.execute(
        "CREATE INDEX ix_stops_geog_gist ON stops USING gist ((geom::geography))"
    )

    op.create_table(
        "subline_stops",
        sa.Column("subline_id", sa.Integer(), primary_key=True),
        sa.Column("sequence", sa.Integer(), primary_key=True),
        sa.Column("stop_id", sa.Integer(), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=True),
        sa.Column("posicion", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["subline_id"], ["sublines.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stop_id"], ["stops.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_subline_stops_stop_id", "subline_stops", ["stop_id"])

    op.create_table(
        "subline_shapes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("subline_id", sa.Integer(), nullable=False),
        sa.Column("idrota", sa.Integer(), nullable=True),
        sa.Column("idseccion", sa.Integer(), nullable=True),
        sa.Column("idramal", sa.Integer(), nullable=True),
        sa.Column("ordem", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.Geometry(
                geometry_type="LINESTRING", srid=4326, spatial_index=False
            ),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["subline_id"], ["sublines.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_subline_shapes_subline_id", "subline_shapes", ["subline_id"])
    op.execute(
        "CREATE INDEX ix_subline_shapes_geom_gist ON subline_shapes USING gist (geom)"
    )

    op.create_table(
        "line_stop_index",
        sa.Column("codigo_linha", sa.String(16), primary_key=True),
        sa.Column("stop_id", sa.Integer(), primary_key=True),
        sa.ForeignKeyConstraint(
            ["codigo_linha"], ["bus_lines.codigo_linha"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["stop_id"], ["stops.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_line_stop_index_stop_id", "line_stop_index", ["stop_id"])

    op.create_table(
        "etl_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(32), server_default="running", nullable=False),
        sa.Column("stats", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_table(
        "user_sessions",
        sa.Column("whatsapp_number", sa.String(32), primary_key=True),
        sa.Column("last_latitude", sa.Float(), nullable=True),
        sa.Column("last_longitude", sa.Float(), nullable=True),
        sa.Column("location_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("selected_codigo_linha", sa.String(16), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "message_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_number", sa.String(32), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=True),
        sa.Column("ai_response", sa.Text(), nullable=True),
        sa.Column("tools_used", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_message_logs_user_number", "message_logs", ["user_number"])
    op.create_index("ix_message_logs_created_at", "message_logs", ["created_at"])

    op.create_table(
        "bus_positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("codigo_linha", sa.String(16), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("codigo_linha", "reported_at", name="uq_bus_position_line_ts"),
    )
    op.create_index("ix_bus_positions_codigo_linha", "bus_positions", ["codigo_linha"])
    op.create_index("ix_bus_positions_reported_at", "bus_positions", ["reported_at"])


def downgrade() -> None:
    op.drop_table("bus_positions")
    op.drop_table("message_logs")
    op.drop_table("user_sessions")
    op.drop_table("etl_runs")
    op.drop_table("line_stop_index")
    op.drop_table("subline_shapes")
    op.drop_table("subline_stops")
    op.drop_table("stops")
    op.drop_table("sublines")
    op.drop_table("bus_lines")
