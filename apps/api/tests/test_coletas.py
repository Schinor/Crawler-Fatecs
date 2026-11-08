"""Painel de saúde do crawler: só para o admin do polo e só a rodada mais recente."""

from datetime import UTC, datetime, timedelta

import pytest

from fatecorg_core.db import sessao
from fatecorg_core.domain import Coleta, Perfil, StatusColeta
from fatecorg_core.repositories import SEM_CURSO, ColetaRepo

SEMANA_1 = datetime(2026, 11, 1, 3, tzinfo=UTC)
SEMANA_2 = SEMANA_1 + timedelta(days=7)


def coleta(quando, status, curso="ads", **detalhe) -> Coleta:
    nome = "-" if curso == SEM_CURSO else curso.upper()
    return Coleta(
        unidade_slug="pompeia", curso_slug=curso, curso_nome=nome, iniciada_em=quando,
        status=status, detalhe=detalhe,
    )  # fmt: skip


@pytest.fixture
def registrar(engine):
    def _registrar(*coletas: Coleta) -> None:
        with sessao(engine) as s:
            for c in coletas:
                ColetaRepo(s).registrar(c)

    return _registrar


@pytest.fixture
def admin(criar_usuario, cabecalho):
    return cabecalho(criar_usuario())


def test_exige_login_de_admin(cliente, criar_usuario, cabecalho):
    assert cliente.get("/coletas").status_code == 401
    consulta = cabecalho(criar_usuario(Perfil.CONSULTA, "c@teste.invalid"))
    coordenador = cabecalho(criar_usuario(Perfil.COORDENADOR, "d@teste.invalid", unidade="pompeia"))
    assert cliente.get("/coletas", headers=consulta).status_code == 403
    assert cliente.get("/coletas", headers=coordenador).status_code == 403


def test_traz_todos_os_resultados_so_da_ultima_rodada_de_cada_curso(cliente, admin, registrar):
    registrar(
        coleta(SEMANA_1, StatusColeta.ERRO_HTTP, erro="HTTP 500"),
        coleta(SEMANA_2, StatusColeta.SEM_MUDANCA, tipo_documento="matriz"),
        coleta(SEMANA_2, StatusColeta.NOVO_PPC, tipo_documento="ppc"),
        coleta(SEMANA_1, StatusColeta.SEM_PPC, curso="big-data"),
    )
    linhas = cliente.get("/coletas", headers=admin).json()
    assert [(c["curso_slug"], c["status"]) for c in linhas] == [
        ("ads", "sem_mudanca"),
        ("ads", "novo_ppc"),
        ("big-data", "sem_ppc"),  # não rodou na semana 2: continua valendo a última que teve
    ]
    assert linhas[0]["iniciada_em"].startswith("2026-11-08")


def test_filtros(cliente, admin, registrar):
    registrar(
        coleta(SEMANA_1, StatusColeta.SEM_PPC),
        coleta(SEMANA_1, StatusColeta.NOVO_PPC, curso="big-data"),
    )
    (achada,) = cliente.get("/coletas", params={"status": "sem_ppc"}, headers=admin).json()
    assert achada["curso_slug"] == "ads"
    assert cliente.get("/coletas", params={"unidade": "marilia"}, headers=admin).json() == []
    assert cliente.get("/coletas", params={"status": "x"}, headers=admin).status_code == 422


def test_falha_na_home_aparece_so_enquanto_e_a_novidade(cliente, admin, registrar):
    registrar(coleta(SEMANA_1, StatusColeta.ERRO_HTTP, curso=SEM_CURSO, erro="home: ConnectError"))
    registrar(coleta(SEMANA_1 - timedelta(days=7), StatusColeta.SEM_MUDANCA))
    linhas = cliente.get("/coletas", headers=admin).json()
    assert {c["curso_slug"] for c in linhas} == {SEM_CURSO, "ads"}

    registrar(coleta(SEMANA_2, StatusColeta.SEM_MUDANCA))
    linhas = cliente.get("/coletas", headers=admin).json()
    assert [c["curso_slug"] for c in linhas] == ["ads"]


def test_banco_sem_coletas(cliente, admin):
    assert cliente.get("/coletas", headers=admin).json() == []
