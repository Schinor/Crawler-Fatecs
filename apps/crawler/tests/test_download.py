import io
import zipfile

import httpx
import pytest

from fatecorg_core.domain import StatusColeta
from fatecorg_crawler.discover import LinkCandidato
from fatecorg_crawler.download import ErroDownload, baixar, detectar_formato

ROBOTS_LIVRE = httpx.Response(404)


def candidato(url: str, drive_id: str | None = None) -> LinkCandidato:
    return LinkCandidato(url=url, texto="PPC", origem="a", drive_id=drive_id)


def test_pdf_direto(fazer_fetcher):
    def handler(req):
        if req.url.path == "/robots.txt":
            return ROBOTS_LIVRE
        return httpx.Response(
            200, content=b"%PDF-1.7 conteudo", headers={"content-type": "application/pdf"}
        )

    with fazer_fetcher(handler) as f:
        arq = baixar(candidato("https://b.net/ppc.pdf"), f)
    assert arq.formato == "pdf"
    assert len(arq.sha256) == 64


def test_drive_com_pagina_de_confirmacao(fazer_fetcher):
    confirmacao = """<form id="download-form" action="https://drive.usercontent.google.com/download">
      <input type="hidden" name="id" value="abc"><input type="hidden" name="confirm" value="t">
    </form>"""

    def handler(req):
        if req.url.path == "/robots.txt":
            return ROBOTS_LIVRE
        if req.url.host == "drive.google.com":
            return httpx.Response(200, text=confirmacao, headers={"content-type": "text/html"})
        assert req.url.params["confirm"] == "t"
        return httpx.Response(200, content=b"%PDF-1.4", headers={"content-type": "application/pdf"})

    with fazer_fetcher(handler) as f:
        arq = baixar(candidato("https://drive.google.com/file/d/abc/view", "abc"), f)
    assert arq.formato == "pdf"


def test_drive_privado_vira_erro_drive(fazer_fetcher):
    def handler(req):
        if req.url.path == "/robots.txt":
            return ROBOTS_LIVRE
        return httpx.Response(
            200, text="<html>Fazer login</html>", headers={"content-type": "text/html"}
        )

    with fazer_fetcher(handler) as f, pytest.raises(ErroDownload) as erro:
        baixar(candidato("https://drive.google.com/file/d/abc/view", "abc"), f)
    assert erro.value.status is StatusColeta.ERRO_DRIVE


def test_drive_bloqueado_pelo_robots_nao_e_contornado(fazer_fetcher):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /file\nDisallow: /\n")
        raise AssertionError("não deveria baixar")

    with fazer_fetcher(handler) as f, pytest.raises(ErroDownload) as erro:
        baixar(candidato("https://drive.google.com/file/d/abc/view", "abc"), f)
    assert erro.value.status is StatusColeta.ERRO_DRIVE
    assert "robots" in erro.value.detalhe


def test_404_vira_erro_http(fazer_fetcher):
    def handler(req):
        return ROBOTS_LIVRE if req.url.path == "/robots.txt" else httpx.Response(404)

    with fazer_fetcher(handler) as f, pytest.raises(ErroDownload) as erro:
        baixar(candidato("https://b.net/sumiu.pdf"), f)
    assert erro.value.status is StatusColeta.ERRO_HTTP


def test_html_no_lugar_do_pdf_vira_nao_pdf(fazer_fetcher):
    def handler(req):
        if req.url.path == "/robots.txt":
            return ROBOTS_LIVRE
        return httpx.Response(200, text="<html>", headers={"content-type": "text/html"})

    with fazer_fetcher(handler) as f, pytest.raises(ErroDownload) as erro:
        baixar(candidato("https://b.net/ppc.pdf"), f)
    assert erro.value.status is StatusColeta.NAO_PDF


def _zip(nomes: list[str]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in nomes:
            z.writestr(n, "x")
    return buf.getvalue()


@pytest.mark.parametrize(
    ("conteudo", "formato"),
    [
        (b"%PDF-1.7", "pdf"),
        (b"\xd0\xcf\x11\xe0resto", "doc"),
        (_zip(["word/document.xml"]), "docx"),
        (_zip(["mimetype", "content.xml"]), "odt"),
        (_zip(["ementa1.pdf", "ementa2.pdf"]), "zip"),
        (b"<html>", None),
    ],
)
def test_detecta_formato_pelo_conteudo(conteudo, formato):
    assert detectar_formato(conteudo) == formato
