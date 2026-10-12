import json

import httpx
import pytest

from fatecorg_crawler.fetch import BloqueadoPorRobots

HTML = b"<html><body>curso</body></html>"


def test_200_salva_html_bruto_e_meta_sem_cookies(fazer_fetcher, settings):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        assert req.headers["User-Agent"].startswith("FatecOrg-Crawler")
        headers = {"content-type": "text/html", "set-cookie": "sessao=segredo"}
        return httpx.Response(200, content=HTML, headers=headers)

    with fazer_fetcher(handler) as f:
        resp = f.get("https://fatec.br/curso", unidade="pompeia")
    assert resp.status == 200
    assert resp.caminho_raw is not None
    assert resp.caminho_raw.read_bytes() == HTML
    meta = json.loads(resp.caminho_raw.with_suffix(".meta.json").read_text())
    assert meta["url"] == "https://fatec.br/curso"
    assert "set-cookie" not in {k.lower() for k in meta["headers"]}
    assert resp.caminho_raw.is_relative_to(settings.data_dir / "raw" / "pompeia")


def test_304_reaproveita_o_html_salvo(fazer_fetcher, settings):
    vistos: list[dict] = []

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        vistos.append(dict(req.headers))
        if req.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(
            200, content=HTML, headers={"content-type": "text/html", "etag": '"v1"'}
        )

    with fazer_fetcher(handler) as f:
        f.get("https://fatec.br/curso", unidade="pompeia")
    # Novo Fetcher lê o cache do disco, como numa nova rodada
    with fazer_fetcher(handler) as f:
        resp = f.get("https://fatec.br/curso", unidade="pompeia")
    assert resp.nao_mudou
    assert resp.conteudo == HTML
    assert vistos[1]["if-none-match"] == '"v1"'


def test_429_tenta_de_novo_com_espera(fazer_fetcher, relogio):
    respostas = iter([httpx.Response(429), httpx.Response(200, content=b"%PDF-1.7")])

    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(404)
        return next(respostas)

    with fazer_fetcher(handler) as f:
        resp = f.get("https://fatec.br/a.pdf", salvar_raw=False)
    assert resp.status == 200
    assert relogio.esperas  # houve backoff


def test_5xx_persistente_devolve_a_ultima_resposta(fazer_fetcher):
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404) if req.url.path == "/robots.txt" else httpx.Response(503)

    with fazer_fetcher(handler) as f:
        assert f.get("https://fatec.br/x", salvar_raw=False).status == 503


def test_robots_bloqueia(fazer_fetcher):
    def handler(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /uc\n")
        raise AssertionError("não deveria acessar URL proibida")

    with fazer_fetcher(handler) as f, pytest.raises(BloqueadoPorRobots):
        f.get("https://drive.google.com/uc?export=download&id=abc")


def test_robots_5xx_proibe_tudo(fazer_fetcher):
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    with fazer_fetcher(handler) as f:
        assert not f.permitido("https://fatec.br/qualquer")


def test_rate_limit_por_host(fazer_fetcher, relogio):
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(404) if req.url.path == "/robots.txt" else httpx.Response(200)

    with fazer_fetcher(handler) as f:
        f.get("https://a.br/1", salvar_raw=False)
        f.get("https://a.br/2", salvar_raw=False)
    # robots, /1 e /2 no mesmo host: duas esperas de 2 s
    assert relogio.esperas == [2.0, 2.0]
