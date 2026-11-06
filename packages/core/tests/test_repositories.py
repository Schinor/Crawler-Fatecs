from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, func, select

from fatecorg_core.db import Base, ColetaDB, CursoDB, sessao
from fatecorg_core.domain import Aviso, Coleta, PPCEncontrado, StatusColeta, TipoAviso, Unidade
from fatecorg_core.repositories import (
    AvisoRepo,
    CatalogoRepo,
    ColetaRepo,
    UnidadeDesconhecida,
    VersaoRepo,
)

SEMANA_1 = datetime(2026, 11, 1, 3, tzinfo=UTC)
SEMANA_2 = datetime(2026, 11, 8, 3, tzinfo=UTC)
POMPEIA = Unidade.model_validate(
    {
        "slug": "pompeia", "nome": "Fatec Pompeia", "cidade": "Pompeia",
        "site_url": "https://fatecpompeia.edu.br", "plataforma": "google_sites",
        "cursos": [{"slug": "ads", "nome": "ADS", "url": "https://fatecpompeia.edu.br/ads"}],
    }
)  # fmt: skip


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessao(engine) as s:
        CatalogoRepo(s).sincronizar([POMPEIA])
    return engine


def ppc(sha: str, curso: str = "ads") -> PPCEncontrado:
    return PPCEncontrado.model_validate(
        {
            "unidade_slug": "pompeia", "curso_slug": curso, "curso_nome": curso.upper(),
            "pagina_url": f"https://fatecpompeia.edu.br/{curso}",
            "arquivo_url": "https://fatecpompeia.edu.br/ppc.pdf", "titulo_link": "PPC",
            "sha256": sha, "caminho_local": f"ppcs/pompeia/{curso}/{sha}.pdf",
            "tamanho_bytes": 10, "coletado_em": SEMANA_1,
        }
    )  # fmt: skip


def aviso(quando: datetime, curso: str = "ads") -> Aviso:
    return Aviso.model_validate(
        {
            "tipo": TipoAviso.DRIVE_BLOQUEADO, "unidade_slug": "pompeia", "curso_slug": curso,
            "curso_nome": curso.upper(), "pagina_url": f"https://fatecpompeia.edu.br/{curso}",
            "arquivo_url": f"https://drive.google.com/file/d/{curso}", "mensagem": "bloqueado",
            "detectado_em": quando, "visto_em": quando,
        }
    )  # fmt: skip


def test_sincronizar_duas_vezes_nao_duplica_e_atualiza_nome(engine):
    renomeada = POMPEIA.model_copy(update={"nome": "Fatec Shunji Nishimura"})
    with sessao(engine) as s:
        CatalogoRepo(s).sincronizar([renomeada])
    with sessao(engine) as s:
        assert CatalogoRepo(s).unidade("pompeia").nome == "Fatec Shunji Nishimura"  # type: ignore[union-attr]
        assert s.scalar(select(func.count()).select_from(CursoDB)) == 1


def test_versao_registrada_vira_sha_conhecido_e_volta_como_dominio(engine):
    with sessao(engine) as s:
        repo = VersaoRepo(s)
        assert not repo.sha_conhecido("pompeia", "ads", "a" * 64)
        repo.registrar(ppc("a" * 64))
        repo.registrar(ppc("b" * 64, curso="big-data"))  # curso fora do seed é criado
    with sessao(engine) as s:
        repo = VersaoRepo(s)
        assert repo.sha_conhecido("pompeia", "ads", "a" * 64)
        assert not repo.sha_conhecido("pompeia", "big-data", "a" * 64)
        (so_ads,) = repo.listar(curso_slug="ads")
        assert so_ads.caminho_local == f"ppcs/pompeia/ads/{'a' * 64}.pdf"
        assert len(repo.listar("pompeia")) == 2


def test_coleta_de_unidade_fora_do_banco_e_recusada(engine):
    coleta = Coleta(
        unidade_slug="garca", curso_slug="-", curso_nome="-", iniciada_em=SEMANA_1,
        status=StatusColeta.ERRO_HTTP,
    )  # fmt: skip
    with pytest.raises(UnidadeDesconhecida), sessao(engine) as s:
        ColetaRepo(s).registrar(coleta)


def test_coleta_da_home_fica_sem_curso(engine):
    coleta = Coleta(
        unidade_slug="pompeia", curso_slug="-", curso_nome="-", iniciada_em=SEMANA_1,
        status=StatusColeta.ERRO_HTTP, detalhe={"erro": "home: ConnectError"},
    )  # fmt: skip
    with sessao(engine) as s:
        ColetaRepo(s).registrar(coleta)
    with sessao(engine) as s:
        (db,) = s.scalars(select(ColetaDB))
        assert db.curso_id is None
        assert db.detalhe == {"erro": "home: ConnectError"}


def test_aviso_abre_uma_vez_renova_e_resolve_so_quando_o_curso_e_lido(engine):
    lidos = {("pompeia", "ads")}
    with sessao(engine) as s:
        r = AvisoRepo(s).atualizar([aviso(SEMANA_1)], lidos, SEMANA_1)
        assert len(r.novos) == 1
    with sessao(engine) as s:
        r = AvisoRepo(s).atualizar([aviso(SEMANA_2)], lidos, SEMANA_2)
        assert r.novos == []
        (aberto,) = AvisoRepo(s).abertos("pompeia")
        assert aberto.visto_em.replace(tzinfo=UTC) == SEMANA_2
        assert aberto.detectado_em.replace(tzinfo=UTC) == SEMANA_1
    with sessao(engine) as s:
        r = AvisoRepo(s).atualizar([], set(), SEMANA_2)  # curso não foi lido: continua aberto
        assert r.resolvidos == []
        r = AvisoRepo(s).atualizar([], lidos, SEMANA_2)
        assert len(r.resolvidos) == 1
        assert AvisoRepo(s).abertos() == []
    with sessao(engine) as s:  # voltou a aparecer: aviso novo, o antigo fica no histórico
        assert len(AvisoRepo(s).atualizar([aviso(SEMANA_2)], lidos, SEMANA_2).novos) == 1
