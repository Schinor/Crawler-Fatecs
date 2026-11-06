"""Tabelas em SQLite (rápido, roda sempre) e migrations no Postgres (só com TEST_DATABASE_URL)."""

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from fatecorg_core.db import AvisoDB, Base, CursoDB, PPCVersaoDB, UnidadeDB, sessao
from fatecorg_core.domain import Plataforma, TipoAviso, TipoDocumento

RAIZ = Path(__file__).resolve().parents[3]
AGORA = datetime(2026, 11, 6, 3, tzinfo=UTC)


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    return engine


def _curso(s) -> CursoDB:
    unidade = UnidadeDB(
        slug="pompeia", nome="Fatec Pompeia", cidade="Pompeia",
        site_url="https://fatecpompeia.edu.br", plataforma=Plataforma.GOOGLE_SITES,
    )  # fmt: skip
    curso = CursoDB(unidade=unidade, slug="ads", nome="ADS")
    s.add(curso)
    s.flush()
    return curso


def _versao(curso: CursoDB, sha: str) -> PPCVersaoDB:
    return PPCVersaoDB(
        curso=curso, tipo_documento=TipoDocumento.PPC, sha256=sha, formato="pdf",
        tamanho_bytes=10, chave_arquivo=f"ppcs/pompeia/ads/{sha}.pdf", coletado_em=AGORA,
    )  # fmt: skip


def _aviso(curso: CursoDB, resolvido_em: datetime | None = None) -> AvisoDB:
    return AvisoDB(
        tipo=TipoAviso.DRIVE_BLOQUEADO, curso=curso, tipo_documento=TipoDocumento.PPC,
        pagina_url="https://x/ads", arquivo_url="https://drive.google.com/file/d/abc",
        mensagem="bloqueado", detectado_em=AGORA, visto_em=AGORA, resolvido_em=resolvido_em,
    )  # fmt: skip


def test_versao_guarda_enum_como_texto_e_campos_vazios(engine):
    with sessao(engine) as s:
        s.add(_versao(_curso(s), "a" * 64))
    with engine.connect() as c:
        tipo, campos = c.execute(text("SELECT tipo_documento, campos FROM ppc_versao")).one()
    assert tipo == "ppc"
    assert campos == "{}"


def test_mesmo_sha_no_mesmo_curso_e_rejeitado(engine):
    with pytest.raises(IntegrityError), sessao(engine) as s:
        curso = _curso(s)
        s.add_all([_versao(curso, "a" * 64), _versao(curso, "a" * 64)])


def test_so_um_aviso_aberto_por_documento(engine):
    with sessao(engine) as s:
        curso = _curso(s)
        s.add_all([_aviso(curso, resolvido_em=AGORA), _aviso(curso, resolvido_em=AGORA)])
        s.add(_aviso(curso))  # resolvidos ficam como histórico; um aberto é permitido
    with pytest.raises(IntegrityError), sessao(engine) as s:
        s.add(_aviso(s.get_one(CursoDB, 1)))


def test_enum_invalido_e_barrado_pelo_check(engine):
    with sessao(engine) as s:
        _curso(s)
    with pytest.raises(IntegrityError), engine.begin() as c:
        c.execute(text("UPDATE unidade SET plataforma = 'joomla'"))


@pytest.mark.postgres
def test_migrations_sobem_descem_e_batem_com_as_tabelas():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("defina TEST_DATABASE_URL (Postgres descartável) para testar as migrations")
    cfg = Config(str(RAIZ / "alembic.ini"))
    cfg.attributes["url"] = url
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    command.check(cfg)  # falha se as tabelas mudaram sem migration
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
