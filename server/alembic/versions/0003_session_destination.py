"""guardar o destino do passageiro na sessão

Sem isso, "e quanto tempo falta?" logo depois de um planejamento recalculava a
resposta pela parada mais próxima e contradizia o que acabara de ser dito — o
mesmo ônibus, dois horários diferentes, porque eram duas paradas diferentes.

Guardando o destino, a pergunta de horário replaneja a *mesma* viagem.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_sessions", sa.Column("destino_texto", sa.String(255), nullable=True)
    )
    op.add_column(
        "user_sessions", sa.Column("destino_latitude", sa.Float(), nullable=True)
    )
    op.add_column(
        "user_sessions", sa.Column("destino_longitude", sa.Float(), nullable=True)
    )
    op.add_column(
        "user_sessions",
        sa.Column("destino_updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_sessions", "destino_updated_at")
    op.drop_column("user_sessions", "destino_longitude")
    op.drop_column("user_sessions", "destino_latitude")
    op.drop_column("user_sessions", "destino_texto")
