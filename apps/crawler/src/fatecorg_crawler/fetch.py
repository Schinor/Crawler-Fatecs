"""HTTP educado: robots.txt, rate limit por host, retries, cache condicional e HTML bruto salvo."""

import hashlib
import ipaddress
import json
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    retry_if_result,
    stop_after_attempt,
    wait_exponential,
)

from fatecorg_crawler.config import CrawlerSettings

STATUS_RETENTAVEIS = {429, 500, 502, 503, 504}


class BloqueadoPorRobots(Exception):
    """A URL é proibida pelo robots.txt do host. Nunca contornar."""


class DestinoBloqueado(httpx.RequestError):
    """Redirect ou link para endereço interno (loopback, rede privada, metadados de nuvem)."""


class RespostaGrande(httpx.RequestError):
    """Resposta acima de CRAWLER_MAX_MB_RESPOSTA: não é carregada na memória."""


def endereco_interno(host: str, *, resolver_dns: bool) -> bool:
    """True se o host é ou resolve para um IP que o crawler nunca deve acessar."""
    host = host.strip("[]").lower()
    if host == "localhost" or host.endswith((".localhost", ".internal", ".local")):
        return True
    try:
        ips = [ipaddress.ip_address(host)]
    except ValueError:
        if not resolver_dns:
            return False
        try:
            ips = [ipaddress.ip_address(i[4][0]) for i in socket.getaddrinfo(host, None)]
        except (socket.gaierror, ValueError):
            return False  # host inexistente: a própria requisição vai falhar
    return any(
        ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved
        or ip.is_multicast or ip.is_unspecified
        for ip in ips
    )  # fmt: skip


@dataclass
class Resposta:
    url: str  # URL final, depois dos redirects
    status: int  # 200, 304, 404...
    content_type: str
    conteudo: bytes
    etag: str | None
    last_modified: str | None
    caminho_raw: Path | None  # onde o HTML foi salvo

    @property
    def ok(self) -> bool:
        return self.status in (200, 304)

    @property
    def nao_mudou(self) -> bool:
        return self.status == 304

    def texto(self) -> str:
        return self.conteudo.decode("utf-8", errors="replace")


def _host(url: str) -> str:
    return urlsplit(url).netloc.lower()


def sha1_url(url: str) -> str:
    return hashlib.sha1(url.encode(), usedforsecurity=False).hexdigest()  # só nome de arquivo


class Fetcher:
    def __init__(
        self,
        settings: CrawlerSettings,
        *,
        transport: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
        relogio: Callable[[], float] = time.monotonic,
    ):
        self.settings = settings
        self._dormir = dormir
        self._relogio = relogio
        self._ultimo_acesso: dict[str, float] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._agente = settings.user_agent.split("/")[0]
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=settings.timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            transport=transport,
            event_hooks={"request": [self._conferir_destino]},
        )
        self._cache_path = settings.data_dir / "cache" / "http.json"
        self._cache: dict[str, dict[str, str]] = (
            json.loads(self._cache_path.read_text(encoding="utf-8"))
            if self._cache_path.exists()
            else {}
        )

    # ------------------------------------------------------------ ciclo de vida
    def __enter__(self) -> "Fetcher":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()
        self._salvar_cache()

    # ------------------------------------------------------------ robots
    def permitido(self, url: str) -> bool:
        """Consulta o robots.txt do host (com cache). 4xx: livre; 5xx ou erro: tudo proibido."""
        partes = urlsplit(url)
        host = partes.netloc.lower()
        if host not in self._robots:
            robots_url = f"{partes.scheme}://{partes.netloc}/robots.txt"
            try:
                r = self._requisitar("GET", robots_url, {})
            except httpx.TransportError:
                r = None
            if r is not None and r.status_code == 200:
                parser = RobotFileParser()
                parser.parse(r.text.splitlines())
                self._robots[host] = parser
            elif r is not None and 400 <= r.status_code < 500:
                self._robots[host] = None  # sem robots.txt: tudo permitido
            else:
                parser = RobotFileParser()
                parser.parse(["User-agent: *", "Disallow: /"])  # robots indisponível: tudo proibido
                self._robots[host] = parser
        parser = self._robots[host]
        return parser is None or parser.can_fetch(self._agente, url)

    def _conferir_destino(self, request: httpx.Request) -> None:
        """Roda em toda requisição, inclusive nos redirects: o destino final também precisa
        respeitar o robots.txt e não pode ser endereço interno (achados C-1 do pentest)."""
        if endereco_interno(request.url.host, resolver_dns=self.settings.resolver_dns_destino):
            raise DestinoBloqueado(
                f"destino interno bloqueado: {request.url.host}", request=request
            )
        url = str(request.url)
        if request.url.path != "/robots.txt" and not self.permitido(url):
            raise BloqueadoPorRobots(url)

    # ------------------------------------------------------------ requisição
    def get(
        self,
        url: str,
        *,
        unidade: str | None = None,
        salvar_raw: bool = True,
        condicional: bool = True,
    ) -> Resposta:
        if not self.permitido(url):
            raise BloqueadoPorRobots(url)

        headers: dict[str, str] = {}
        anterior = self._cache.get(url, {}) if condicional else {}
        if anterior.get("etag"):
            headers["If-None-Match"] = anterior["etag"]
        if anterior.get("last_modified"):
            headers["If-Modified-Since"] = anterior["last_modified"]

        r = self._requisitar("GET", url, headers)
        content_type = r.headers.get("content-type", "")

        if r.status_code == 304 and anterior.get("caminho_raw"):
            caminho = Path(anterior["caminho_raw"])
            conteudo = caminho.read_bytes() if caminho.exists() else b""
            return Resposta(
                str(r.url), 304, anterior.get("content_type") or content_type, conteudo,
                anterior.get("etag"), anterior.get("last_modified"), caminho,
            )  # fmt: skip

        resposta = Resposta(
            url=str(r.url),
            status=r.status_code,
            content_type=content_type,
            conteudo=r.content,
            etag=r.headers.get("etag"),
            last_modified=r.headers.get("last-modified"),
            caminho_raw=None,
        )
        eh_html = "html" in content_type
        if r.status_code == 200 and salvar_raw and eh_html and unidade:
            resposta.caminho_raw = self._salvar_raw(url, unidade, resposta, dict(r.headers))
        if (
            r.status_code == 200
            and resposta.caminho_raw
            and (resposta.etag or resposta.last_modified)
        ):
            self._cache[url] = {
                k: v
                for k, v in {
                    "etag": resposta.etag,
                    "last_modified": resposta.last_modified,
                    "content_type": content_type,
                    "caminho_raw": str(resposta.caminho_raw),
                }.items()
                if v
            }
        return resposta

    def _esperar_vez(self, host: str) -> None:
        ultimo = self._ultimo_acesso.get(host)
        if ultimo is not None:
            falta = self.settings.delay_seconds - (self._relogio() - ultimo)
            if falta > 0:
                self._dormir(falta)
        self._ultimo_acesso[host] = self._relogio()

    def _requisitar(self, metodo: str, url: str, headers: dict[str, str]) -> httpx.Response:
        limite = self.settings.max_mb_resposta * 1024 * 1024

        def tentar() -> httpx.Response:
            self._esperar_vez(_host(url))
            # Lê em blocos e para no limite, em vez de carregar qualquer tamanho (achado C-2)
            with self._client.stream(metodo, url, headers=headers) as r:
                declarado = r.headers.get("content-length", "")
                if declarado.isdigit() and int(declarado) > limite:
                    raise RespostaGrande(f"{declarado} bytes em {r.url}", request=r.request)
                partes, total = [], 0
                for bloco in r.iter_bytes():
                    total += len(bloco)
                    if total > limite:
                        raise RespostaGrande(
                            f"mais de {limite} bytes em {r.url}", request=r.request
                        )
                    partes.append(bloco)
            # Corpo já descomprimido: sem os cabeçalhos de codificação e tamanho originais
            cabecalhos = [
                (k, v) for k, v in r.headers.multi_items()
                if k.lower() not in {"content-encoding", "content-length", "transfer-encoding"}
            ]  # fmt: skip
            return httpx.Response(
                r.status_code, headers=cabecalhos, content=b"".join(partes), request=r.request
            )

        tentativas = Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=self.settings.delay_seconds, max=60),
            retry=(
                retry_if_exception_type(httpx.TransportError)
                | retry_if_result(lambda r: r.status_code in STATUS_RETENTAVEIS)
            ),
            sleep=self._dormir,
            retry_error_callback=lambda estado: estado.outcome.result(),  # type: ignore[union-attr]
        )
        return tentativas(tentar)

    # ------------------------------------------------------------ persistência
    def _salvar_raw(self, url: str, unidade: str, resp: Resposta, headers: dict) -> Path:
        agora = datetime.now(UTC)
        pasta = self.settings.data_dir / "raw" / unidade / agora.strftime("%Y-%m-%d")
        pasta.mkdir(parents=True, exist_ok=True)
        base = pasta / sha1_url(url)
        caminho = base.with_suffix(".html")
        caminho.write_bytes(resp.conteudo)
        meta = {
            "url": url,
            "url_final": resp.url,
            "status": resp.status,
            "coletado_em": agora.isoformat(),
            "headers": {k: v for k, v in headers.items() if k.lower() != "set-cookie"},
        }
        base.with_suffix(".meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return caminho

    def _salvar_cache(self) -> None:
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache_path.write_text(json.dumps(self._cache, indent=2), encoding="utf-8")
