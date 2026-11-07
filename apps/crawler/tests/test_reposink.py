"""Pipeline completo com o RepoSink da Fase 2 (SQLite + pasta no lugar de Postgres + Garage)."""

import httpx
from sqlalchemy import create_engine, func, select, text

from fatecorg_core.db import Base, ColetaDB, sessao
from fatecorg_core.domain import StatusColeta, TipoAviso, Unidade
from fatecorg_core.repositories import VersaoRepo
from fatecorg_core.storage import LocalStorage
from fatecorg_crawler.importar import indexar_textos
from fatecorg_crawler.pipeline import Coletor
from fatecorg_crawler.sink import RepoSink

UNIDADE = Unidade.model_validate(
    {
        "slug": "marilia", "nome": "Fatec Marília", "cidade": "Marília",
        "site_url": "https://fatec.br", "plataforma": "wordpress",
        "cursos": [
            {"slug": "alimentos", "nome": "Alimentos", "url": "https://fatec.br/alimentos/"},
            {"slug": "vazio", "nome": "Sem documentos", "url": "https://fatec.br/vazio/"},
        ],
    }
)  # fmt: skip
MATRIZ = '<a href="https://b.net/Grade-C31.pdf">Grade C31 – 2014-2 até atual</a>'
DRIVE = """<html><body>
  <a href="https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/view">PPC Alimentos</a>
</body></html>"""


def montar(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'banco.db'}")
    Base.metadata.create_all(engine)
    storage = LocalStorage(tmp_path / "garage")
    return engine, storage, RepoSink(engine, storage, [UNIDADE])


def handler(pdf: bytes):
    def responder(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/alimentos/":
            return httpx.Response(200, text=MATRIZ, headers={"content-type": "text/html"})
        if req.url.host == "b.net":
            return httpx.Response(200, content=pdf, headers={"content-type": "application/pdf"})
        return httpx.Response(200, text="<p>nada</p>", headers={"content-type": "text/html"})

    return responder


def rodar(settings, fazer_fetcher, sink, responder):
    settings.dominios_arquivos = ["b.net", "drive.google.com"]
    with fazer_fetcher(responder) as f:
        coletas = Coletor(settings, f, sink).coletar_unidade(UNIDADE)
    return coletas, sink.atualizar_avisos(coletas)


def test_duas_rodadas_gravam_uma_versao_no_banco_e_o_arquivo_no_storage(
    tmp_path, settings, fazer_fetcher, pdf_com_texto
):
    engine, storage, sink = montar(tmp_path)
    responder = handler(pdf_com_texto("Matriz curricular " * 50))
    rodar(settings, fazer_fetcher, sink, responder)
    coletas, _ = rodar(settings, fazer_fetcher, sink, responder)

    assert {c.status for c in coletas} == {StatusColeta.SEM_MUDANCA, StatusColeta.SEM_PPC}
    with sessao(engine) as s:
        (versao,) = VersaoRepo(s).listar("marilia")
        assert s.scalar(select(func.count()).select_from(ColetaDB)) == 4
    assert storage.ler(versao.caminho_local).startswith(b"%PDF")
    assert versao.caminho_texto is not None
    assert b"Matriz curricular" in storage.ler(versao.caminho_texto)
    assert not (settings.data_dir / "ppcs").exists()  # nada vai para data/


def test_drive_bloqueado_vira_aviso_no_banco(tmp_path, settings, fazer_fetcher):
    _, _, sink = montar(tmp_path)

    def responder(req: httpx.Request) -> httpx.Response:
        if req.url.host == "drive.google.com" and req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /uc\n")
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        if req.url.path == "/alimentos/":
            return httpx.Response(200, text=DRIVE, headers={"content-type": "text/html"})
        return httpx.Response(200, text="<p>nada</p>", headers={"content-type": "text/html"})

    _, primeira = rodar(settings, fazer_fetcher, sink, responder)
    (aviso,) = primeira.novos
    assert aviso.tipo is TipoAviso.DRIVE_BLOQUEADO
    assert aviso.curso_slug == "alimentos"

    _, segunda = rodar(settings, fazer_fetcher, sink, responder)
    assert segunda.novos == []  # não notifica de novo
    assert len(sink.avisos_abertos()) == 1


def test_importar_a_fase_1_duas_vezes_nao_duplica(tmp_path, settings, fazer_fetcher, pdf_com_texto):
    from fatecorg_crawler.importar import importar
    from fatecorg_crawler.sink import JsonlSink

    jsonl = JsonlSink(settings.data_dir)
    rodar(settings, fazer_fetcher, jsonl, handler(pdf_com_texto("Matriz curricular " * 50)))
    engine, storage, banco = montar(tmp_path)

    primeira = importar(jsonl, banco)
    assert primeira["versoes_importadas"] == 1
    assert primeira["arquivos_enviados"] == 2  # PDF + texto
    assert primeira["coletas_importadas"] == 2

    segunda = importar(jsonl, banco)
    assert segunda["versoes_importadas"] == 0
    assert segunda["coletas_importadas"] == 0
    (versao,) = jsonl.ler_ppcs()
    assert storage.ler(versao.caminho_local) == jsonl.arquivos.ler(versao.caminho_local)


def test_texto_vai_para_o_banco_e_a_busca_acha(tmp_path, settings, fazer_fetcher, pdf_com_texto):
    engine, _, sink = montar(tmp_path)
    rodar(settings, fazer_fetcher, sink, handler(pdf_com_texto("Estágio supervisionado " * 40)))
    with sessao(engine) as s:
        (r,) = VersaoRepo(s).buscar_no_texto("estagio")
    assert r.ppc.unidade_slug == "marilia"
    assert any(t.destaque for t in r.trechos)


def test_indexar_preenche_o_texto_das_versoes_antigas(
    tmp_path, settings, fazer_fetcher, pdf_com_texto
):
    engine, storage, sink = montar(tmp_path)
    rodar(settings, fazer_fetcher, sink, handler(pdf_com_texto("Extensão curricular " * 40)))
    with engine.begin() as c:  # simula uma versão gravada antes da migration 0002
        c.execute(text("UPDATE ppc_versao SET texto = NULL"))
    with sessao(engine) as s:
        assert VersaoRepo(s).buscar_no_texto("extensao") == []

    assert indexar_textos(engine, storage) == 1
    assert indexar_textos(engine, storage) == 0  # pode rodar de novo
    with sessao(engine) as s:
        assert len(VersaoRepo(s).buscar_no_texto("extensao")) == 1
