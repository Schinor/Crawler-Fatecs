"""login: usuários, sessões e autor do upload

`usuario` e `sessao_login` (refresh tokens, só o hash) para o login com perfis (A1), e
`ppc_versao.enviado_por_id` para saber quem fez cada upload manual (achado A-7 do pentest).

Depois de aplicar, crie o primeiro acesso: `make usuario E=... N="..." P=admin_polo`.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-08 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "usuario",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("nome", sa.String(length=200), nullable=False),
        sa.Column("senha_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "perfil",
            sa.Enum(
                "consulta",
                "coordenador",
                "admin_polo",
                name="perfil",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=False,
        ),
        sa.Column("unidade_id", sa.Integer(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False),
        sa.Column("falhas_login", sa.Integer(), nullable=False),
        sa.Column("bloqueado_ate", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["unidade_id"],
            ["unidade.id"],
            name=op.f("fk_usuario_unidade_id_unidade"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_usuario")),
        sa.UniqueConstraint("email", name=op.f("uq_usuario_email")),
    )
    op.create_table(
        "sessao_login",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("token_sha256", sa.String(length=64), nullable=False),
        sa.Column("criada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expira_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("girada_em", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["usuario_id"],
            ["usuario.id"],
            name=op.f("fk_sessao_login_usuario_id_usuario"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessao_login")),
        sa.UniqueConstraint("token_sha256", name=op.f("uq_sessao_login_token_sha256")),
    )
    op.create_index(
        op.f("ix_sessao_login_usuario_id"), "sessao_login", ["usuario_id"], unique=False
    )
    op.add_column("ppc_versao", sa.Column("enviado_por_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_ppc_versao_enviado_por_id_usuario"),
        "ppc_versao",
        "usuario",
        ["enviado_por_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_ppc_versao_enviado_por_id_usuario"), "ppc_versao", type_="foreignkey"
    )
    op.drop_column("ppc_versao", "enviado_por_id")
    op.drop_index(op.f("ix_sessao_login_usuario_id"), table_name="sessao_login")
    op.drop_table("sessao_login")
    op.drop_table("usuario")
