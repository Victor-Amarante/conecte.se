from datetime import datetime, timezone

from geoalchemy2 import Geometry
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------
# Transit network (populated by the RUMO ETL)
# --------------------------------------------------------------------------


class BusLine(Base):
    """A bus line as published by RUMO, keyed by its public code (e.g. "011")."""

    __tablename__ = "bus_lines"

    codigo_linha: Mapped[str] = mapped_column(String(16), primary_key=True)
    nome: Mapped[str] = mapped_column(String(255))
    nome_completo: Mapped[str] = mapped_column(String(320))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(),
    )

    sublines: Mapped[list["Subline"]] = relationship(
        back_populates="line", cascade="all, delete-orphan"
    )


class Subline(Base):
    """A variant of a line ("Principal", "Atende Loreto II no sentido 1", ...).

    The primary key is RUMO's ``codigoSublinha``, which is what the
    ``json_paradas_linha`` and ``json_shape`` endpoints take.
    """

    __tablename__ = "sublines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    codigo_linha: Mapped[str] = mapped_column(
        ForeignKey("bus_lines.codigo_linha", ondelete="CASCADE"), index=True
    )
    label: Mapped[str | None] = mapped_column(String(16))
    descricao: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(),
    )

    line: Mapped[BusLine] = relationship(back_populates="sublines")


class Stop(Base):
    """A physical bus stop. ``id`` and ``nodo`` both come from RUMO.

    ``nodo`` is the join key between the ``json_mapa_paradas`` inventory and the
    per-subline itineraries returned by ``json_paradas_linha``.
    """

    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    nodo: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    codigo: Mapped[str] = mapped_column(String(64), index=True)
    nome: Mapped[str | None] = mapped_column(String(255))
    referencia: Mapped[str | None] = mapped_column(Text)
    clase: Mapped[int] = mapped_column(Integer)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(),
    )


# NOTE: proximity queries use ``geom::geography``, and a plain geometry GiST
# index is not usable by a geography predicate. The migration therefore creates
# a functional index on the cast; see alembic/versions/0001_initial_postgis.py.


class SublineStop(Base):
    """One ordered entry of a subline's itinerary."""

    __tablename__ = "subline_stops"

    subline_id: Mapped[int] = mapped_column(
        ForeignKey("sublines.id", ondelete="CASCADE"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    stop_id: Mapped[int] = mapped_column(
        ForeignKey("stops.id", ondelete="CASCADE"), index=True
    )
    orden: Mapped[int | None] = mapped_column(Integer)
    posicion: Mapped[int | None] = mapped_column(Integer)


class SublineShape(Base):
    """A polyline segment of a subline's drawn route."""

    __tablename__ = "subline_shapes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    subline_id: Mapped[int] = mapped_column(
        ForeignKey("sublines.id", ondelete="CASCADE"), index=True
    )
    idrota: Mapped[int | None] = mapped_column(Integer)
    idseccion: Mapped[int | None] = mapped_column(Integer)
    idramal: Mapped[int | None] = mapped_column(Integer)
    ordem: Mapped[int] = mapped_column(Integer, default=0)
    geom: Mapped[object] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=True)
    )


class LineStopIndex(Base):
    """Reverse index line -> stop, derived from ``subline_stops``.

    Materialised by the ETL so "which lines serve this stop?" is a single
    indexed join instead of a walk through every subline itinerary.
    """

    __tablename__ = "line_stop_index"

    codigo_linha: Mapped[str] = mapped_column(
        ForeignKey("bus_lines.codigo_linha", ondelete="CASCADE"), primary_key=True
    )
    stop_id: Mapped[int] = mapped_column(
        ForeignKey("stops.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class ETLRun(Base):
    """Audit trail for RUMO synchronisation runs."""

    __tablename__ = "etl_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="running")
    stats: Mapped[dict | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)


# --------------------------------------------------------------------------
# Conversation state
# --------------------------------------------------------------------------


class UserSession(Base):
    """Per-user state that outlives a single WhatsApp message."""

    __tablename__ = "user_sessions"

    whatsapp_number: Mapped[str] = mapped_column(String(32), primary_key=True)
    last_latitude: Mapped[float | None] = mapped_column(Float)
    last_longitude: Mapped[float | None] = mapped_column(Float)
    location_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    selected_codigo_linha: Mapped[str | None] = mapped_column(String(16))
    # Para onde o passageiro disse que vai. Guardar isso é o que permite
    # responder "e agora, quanto tempo falta?" replanejando a mesma viagem, em
    # vez de recalcular por proximidade e contradizer a resposta anterior.
    destino_texto: Mapped[str | None] = mapped_column(String(255))
    destino_latitude: Mapped[float | None] = mapped_column(Float)
    destino_longitude: Mapped[float | None] = mapped_column(Float)
    destino_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow,
        server_default=func.now(),
    )


class MessageLog(Base):
    __tablename__ = "message_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_number: Mapped[str] = mapped_column(String(32), index=True)
    user_message: Mapped[str | None] = mapped_column(Text)
    ai_response: Mapped[str | None] = mapped_column(Text)
    tools_used: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), index=True
    )
