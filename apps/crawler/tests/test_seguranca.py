"""Regressões dos achados do pentest no crawler (docs/seguranca.md)."""

import gzip

import httpx
import pytest

from fatecorg_crawler.discover import LinkCandidato
from fatecorg_crawler.download import ErroDownload, baixar
from fatecorg_crawler.fetch import (
    BloqueadoPorRobots,
    DestinoBloqueado,
    RespostaGrande,
    endereco_interno,
)

SEM_ROBOTS = httpx.Response(404)


@pytest.mark.parametrize(
    "host",
    ["127.0.0.1", "localhost", "10.0.0.5", "192.168.1.1", "169.254.169.254", "[::1]", "x.internal"],
)
def test_c1_enderecos_internos_sao_reconhecidos(host):
    assert endereco_interno(host, resolver_dns=False)


def test_c1_host_publico_passa():
    assert not endereco_interno("fatecpompeia.edu.br", resolver_dns=False)
    assert not endereco_interno("8.8.8.8", resolver_dns=False)


def test_c1_redirect_para_metadados_da_nuvem_e_bloqueado(fazer_fetcher):
    def handler(req):
        if req.url.path == "/robots.txt":
            return SEM_ROBOTS
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/meta-data/"})

    with fazer_fetcher(handler) as f, pytest.raises(DestinoBloqueado):
        f.get("https://fatec.br/curso/")


def test_c1_redirect_para_caminho_proibido_pelo_robots_e_bloqueado(fazer_fetcher):
    def handler(req):
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /privado/\n")
        if req.url.path == "/curso/":
            return httpx.Response(302, headers={"location": "/privado/ppc.pdf"})
        raise AssertionError(f"acessou {req.url} mesmo proibido pelo robots.txt")

    with fazer_fetcher(handler) as f, pytest.raises(BloqueadoPorRobots):
        f.get("https://fatec.br/curso/")


def test_c2_content_length_acima_do_limite_nao_e_lido(settings, fazer_fetcher):
    settings.max_mb_resposta = 1

    def handler(req):
        if req.url.path == "/robots.txt":
            return SEM_ROBOTS
        return httpx.Response(200, headers={"content-length": str(5 * 1024 * 1024)}, content=b"x")

    with fazer_fetcher(handler) as f, pytest.raises(RespostaGrande):
        f.get("https://fatec.br/enorme.pdf")


def test_c2_corpo_sem_content_length_para_no_limite(settings, fazer_fetcher):
    settings.max_mb_resposta = 1

    def blocos():
        for _ in range(3):
            yield b"0" * (1024 * 1024)

    def handler(req):
        if req.url.path == "/robots.txt":
            return SEM_ROBOTS
        return httpx.Response(200, content=blocos())

    with fazer_fetcher(handler) as f, pytest.raises(RespostaGrande):
        f.get("https://fatec.br/enorme.pdf")


def test_c2_resposta_gzip_continua_legivel(fazer_fetcher):
    def handler(req):
        if req.url.path == "/robots.txt":
            return SEM_ROBOTS
        return httpx.Response(
            200,
            content=gzip.compress(b"<p>Matriz curricular</p>"),
            headers={"content-encoding": "gzip", "content-type": "text/html; charset=utf-8"},
        )

    with fazer_fetcher(handler) as f:
        assert "Matriz curricular" in f.get("https://fatec.br/curso/", salvar_raw=False).texto()


def test_c3_confirmacao_do_drive_para_outro_dominio_e_recusada(fazer_fetcher):
    falso = '<form id="download-form" action="http://malicioso.example/coleta"></form>'

    def handler(req):
        if req.url.path == "/robots.txt":
            return SEM_ROBOTS
        if req.url.host == "drive.google.com":
            return httpx.Response(200, text=falso, headers={"content-type": "text/html"})
        raise AssertionError(f"seguiu o formulário até {req.url}")

    candidato = LinkCandidato(
        url="https://drive.google.com/file/d/abc/view", texto="PPC", origem="a", drive_id="abc"
    )
    with fazer_fetcher(handler) as f, pytest.raises(ErroDownload, match="malicioso.example"):
        baixar(candidato, f)
