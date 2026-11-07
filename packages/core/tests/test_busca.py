from datetime import timedelta

import pytest
from sqlalchemy import create_engine

from fatecorg_core.busca import Trecho, buscar_simples, termos, trechos_do_headline
from fatecorg_core.db import Base, sessao
from fatecorg_core.domain import TipoDocumento
from fatecorg_core.repositories import CatalogoRepo, VersaoRepo

from .test_repositories import POMPEIA, SEMANA_1, ppc

ESTAGIO = "O estágio supervisionado é obrigatório.\n\nCarga horária de 240 horas no 5º semestre."


def test_termos_sem_acento_e_sem_operadores():
    assert termos('"Estágio Supervisionado" or TCC -x') == ["estagio", "supervisionado", "tcc"]


def test_trechos_do_headline_viram_dados():
    assert trechos_do_headline("O ⟦estágio⟧ é  obrigatório … carga do ⟦estágio⟧") == [
        Trecho("O "),
        Trecho("estágio", True),
        Trecho(" é obrigatório … carga do "),
        Trecho("estágio", True),
    ]


def test_busca_simples_ignora_acento_e_exige_todos_os_termos():
    achado = buscar_simples(ESTAGIO, "ESTAGIO obrigatorio")
    assert achado is not None
    relevancia, trechos = achado
    assert relevancia == 2
    assert [t.texto for t in trechos if t.destaque] == ["estágio", "obrigatório"]
    assert "".join(t.texto for t in trechos).startswith("O estágio supervisionado")
    assert buscar_simples(ESTAGIO, "estagio tcc") is None
    assert buscar_simples(ESTAGIO, "a") is None  # nenhum termo útil


def test_busca_simples_corta_textos_longos_com_reticencias():
    texto = "palavra " * 200 + "estágio " + "outra " * 200
    _, trechos = buscar_simples(texto, "estagio") or (0, [])
    assert trechos[0].texto == "… " and trechos[-1].texto == " …"
    assert len("".join(t.texto for t in trechos)) < 300


@pytest.fixture
def repo_com_textos():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessao(engine) as s:
        CatalogoRepo(s).sincronizar([POMPEIA])
        repo = VersaoRepo(s)
        repo.registrar(ppc("1" * 64), ESTAGIO)
        novo = ppc("2" * 64).model_copy(
            update={"coletado_em": SEMANA_1 + timedelta(days=7), "tipo_documento": "matriz"}
        )
        repo.registrar(novo, "Matriz com estágio e estágio.\x00")
        repo.registrar(ppc("3" * 64), None)  # zip: sem texto
    return engine


def test_repo_busca_no_texto_por_relevancia_e_filtra_por_tipo(repo_com_textos):
    with sessao(repo_com_textos) as s:
        resultados = VersaoRepo(s).buscar_no_texto("estagio")
        assert [r.ppc.sha256[0] for r in resultados] == ["2", "1"]  # 2 ocorrências antes de 1
        so_ppc = VersaoRepo(s).buscar_no_texto("estagio", tipo=TipoDocumento.PPC)
        assert [r.ppc.sha256[0] for r in so_ppc] == ["1"]
        assert VersaoRepo(s).buscar_no_texto("estagio", unidade_slug="marilia") == []


def test_repo_indexa_depois_as_versoes_sem_texto(repo_com_textos):
    with sessao(repo_com_textos) as s:
        repo = VersaoRepo(s)
        assert repo.sem_texto_indexado() == []  # a versão sem texto também não tem chave_texto
        com_chave = ppc("4" * 64).model_copy(update={"caminho_texto": "ppcs/x.txt"})
        repo.registrar(com_chave)
        ((versao_id, chave),) = repo.sem_texto_indexado()
        assert chave == "ppcs/x.txt"
        repo.definir_texto(versao_id, "Trabalho de conclusão")
        assert repo.sem_texto_indexado() == []
        (r,) = repo.buscar_no_texto("conclusao")
        assert r.ppc.sha256 == "4" * 64
