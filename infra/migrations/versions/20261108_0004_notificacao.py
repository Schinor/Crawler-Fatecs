"""notificação de versão nova

`notificacao` guarda as versões que ainda precisam ser avisadas por e-mail (A6) e
`ppc_versao.so_arquivo_mudou` marca a versão cujo texto é igual ao da anterior: não gera aviso.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-08 16:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "ppc_versao",
        sa.Column("so_arquivo_mudou", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_table(
        "notificacao",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ppc_versao_id", sa.Integer(), nullable=False),
        sa.Column("documento_novo", sa.Boolean(), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enviada_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("erro", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["ppc_versao_id"],
            ["ppc_versao.id"],
            name=op.f("fk_notificacao_ppc_versao_id_ppc_versao"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notificacao")),
        sa.UniqueConstraint("ppc_versao_id", name=op.f("uq_notificacao_ppc_versao_id")),
    )


def downgrade() -> None:
    op.drop_table("notificacao")
    op.drop_column("ppc_versao", "so_arquivo_mudou")
