"""drop the unused bus_positions table

A tabela foi criada prevendo histórico de GPS embarcado, mas nada nunca
escreveu nela: o ``BusLocationService`` guarda a última posição em memória, e a
fonte de horários passou a ser o Google Maps, que dispensa rastreamento próprio.
Uma tabela vazia e sem escrita só engana quem abre o banco.

O ``POST /location`` continua funcionando — ele alimenta a memória do processo,
não esta tabela. Se um dia houver rastreamento real e a necessidade de
histórico, vale recriá-la já com quem escreve nela.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_bus_positions_reported_at", table_name="bus_positions")
    op.drop_index("ix_bus_positions_codigo_linha", table_name="bus_positions")
    op.drop_table("bus_positions")


def downgrade() -> None:
    op.create_table(
        "bus_positions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("codigo_linha", sa.String(16), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy", sa.Float(), nullable=True),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "codigo_linha", "reported_at", name="uq_bus_position_line_ts"
        ),
    )
    op.create_index("ix_bus_positions_codigo_linha", "bus_positions", ["codigo_linha"])
    op.create_index("ix_bus_positions_reported_at", "bus_positions", ["reported_at"])
