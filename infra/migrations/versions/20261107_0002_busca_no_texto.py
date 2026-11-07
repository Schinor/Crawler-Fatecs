"""busca no texto dos documentos

Coluna `ppc_versao.texto` e índice full-text em português sem acento: a configuração
`fatecorg_pt` copia a `portuguese` e passa as palavras pelo `unaccent` antes do stemmer, então
"estagio" acha "estágio". O `unaccent` vem no contrib do Postgres (imagem oficial inclui) e é
uma extensão "trusted": o dono do banco pode criá-la.

Depois de aplicar, preencha o texto das versões já gravadas: `fatecorg-crawler indexar`.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-07 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

VETOR = (
    "to_tsvector('fatecorg_pt'::regconfig, coalesce(titulo_link, '') || ' ' || coalesce(texto, ''))"
)


def upgrade() -> None:
    op.add_column("ppc_versao", sa.Column("texto", sa.Text(), nullable=True))
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute("CREATE TEXT SEARCH CONFIGURATION fatecorg_pt (COPY = portuguese)")
    op.execute(
        "ALTER TEXT SEARCH CONFIGURATION fatecorg_pt "
        "ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem"
    )
    op.execute(f"CREATE INDEX ix_ppc_versao_busca ON ppc_versao USING gin ({VETOR})")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_ppc_versao_busca")
    op.execute("DROP TEXT SEARCH CONFIGURATION IF EXISTS fatecorg_pt")
    # A extensão unaccent fica: outras partes do banco podem usá-la e ela não guarda dados
    op.drop_column("ppc_versao", "texto")
