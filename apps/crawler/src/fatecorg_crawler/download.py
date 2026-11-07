"""Baixa o arquivo de um candidato, identifica o formato e calcula o SHA-256."""

import hashlib
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from fatecorg_core.arquivos import detectar_formato
from fatecorg_core.domain import StatusColeta
from fatecorg_crawler.discover import LinkCandidato
from fatecorg_crawler.drive import url_download_direto
from fatecorg_crawler.fetch import BloqueadoPorRobots, Fetcher, Resposta

DOMINIOS_DRIVE = {"drive.google.com", "drive.usercontent.google.com", "docs.google.com"}


@dataclass
class ArquivoBaixado:
    url_origem: str
    conteudo: bytes
    sha256: str
    content_type: str
    formato: str  # pdf, docx, doc, odt, zip


class ErroDownload(Exception):
    def __init__(self, status: StatusColeta, detalhe: str):
        super().__init__(detalhe)
        self.status = status
        self.detalhe = detalhe


def _confirmacao_drive(resp: Resposta) -> str | None:
    """Arquivo grande no Drive devolve página com <form id="download-form">. Monta a URL final."""
    form = BeautifulSoup(resp.texto(), "lxml").find("form", id="download-form")
    if form is None or not form.get("action"):
        return None
    destino = urlsplit(str(form["action"])).netloc.lower()
    if destino not in DOMINIOS_DRIVE:  # achado C-3: o formulário não decide para onde vamos
        raise ErroDownload(StatusColeta.ERRO_DRIVE, f"confirmação do Drive aponta para {destino}")
    campos = {
        str(i.get("name")): str(i.get("value") or "")
        for i in form.find_all("input", attrs={"type": "hidden"})
        if i.get("name")
    }
    return str(httpx.URL(str(form["action"]), params=campos))


def baixar(candidato: LinkCandidato, fetcher: Fetcher) -> ArquivoBaixado:
    eh_drive = candidato.drive_id is not None
    status_erro = StatusColeta.ERRO_DRIVE if eh_drive else StatusColeta.ERRO_HTTP
    url = url_download_direto(candidato.drive_id) if candidato.drive_id else candidato.url

    def buscar(alvo: str) -> Resposta:
        try:
            resp = fetcher.get(alvo, salvar_raw=False, condicional=False)
        except BloqueadoPorRobots as e:
            raise ErroDownload(status_erro, f"bloqueado pelo robots.txt: {e}") from e
        except httpx.HTTPError as e:
            raise ErroDownload(status_erro, f"falha de rede: {e.__class__.__name__}") from e
        if resp.status != 200:
            raise ErroDownload(status_erro, f"HTTP {resp.status} em {alvo}")
        return resp

    resp = buscar(url)
    if eh_drive and "html" in resp.content_type:
        confirmacao = _confirmacao_drive(resp)
        if confirmacao is None:
            # Página de login ou arquivo privado: nunca tentar autenticar
            raise ErroDownload(StatusColeta.ERRO_DRIVE, "Drive devolveu HTML (privado ou removido)")
        resp = buscar(confirmacao)

    formato = detectar_formato(resp.conteudo)
    if formato is None:
        raise ErroDownload(
            StatusColeta.NAO_PDF, f"conteúdo não é documento ({resp.content_type or '?'})"
        )
    return ArquivoBaixado(
        url_origem=candidato.url,
        conteudo=resp.conteudo,
        sha256=hashlib.sha256(resp.conteudo).hexdigest(),
        content_type=resp.content_type,
        formato=formato,
    )
