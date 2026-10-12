"""Encontra documentos curriculares (PPC, matriz, ementário) numa página HTML.

Heurística genérica por pontuação, sem seletor específico por site: o rótulo do link
(texto, title, aria-label) e a URL somam pontos por termos curriculares e perdem pontos por
termos de documentos que não interessam (deliberação, calendário, horário...).
"""

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import unquote, urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

from fatecorg_core.domain import TipoDocumento
from fatecorg_crawler.drive import desembrulhar_redirect_google, extrair_drive_id

LIMIAR = 4
EXTENSOES_DOCUMENTO = (".pdf", ".doc", ".docx", ".odt", ".zip")

# Padrões aplicados sobre texto sem acento e em minúsculas
_PPC = re.compile(r"\bppc\b|projeto\s+pedagogico|plano\s+pedagogico")
_EMENTARIO = re.compile(r"\bementario\b|\bementas?\b")
_MATRIZ = re.compile(r"\bmatriz\b|\bgrade\b|estrutura\s+curricular")
_NEGATIVO = re.compile(
    r"deliberacao|calendario|regulamento|horario|informativo|edital|escala|telefone"
    r"|acervo|\bprova\b|\baula\b|redeps|portaria|resolucao"
)


@dataclass(frozen=True)
class LinkCandidato:
    url: str
    texto: str
    origem: str  # "a" (link) ou "iframe"
    drive_id: str | None
    tipo: TipoDocumento = TipoDocumento.PPC
    pontos: int = 0


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[\s_\-]+", " ", sem_acento.lower())


def _parece_documento(url: str) -> bool:
    caminho = urlsplit(url).path.lower()
    return caminho.endswith(EXTENSOES_DOCUMENTO) or extrair_drive_id(url) is not None


def _rotulo(tag: Tag) -> str:
    partes = [
        tag.get_text(" ", strip=True),
        str(tag.get("title") or ""),
        str(tag.get("aria-label") or ""),
    ]
    return " ".join(p for p in partes if p)


def classificar(rotulo: str, url: str) -> tuple[TipoDocumento | None, int]:
    """Devolve o tipo de documento e a pontuação. Tipo None = não é documento curricular."""
    texto = _normalizar(rotulo)
    nome_arquivo = _normalizar(unquote(urlsplit(url).path.rsplit("/", 1)[-1]))
    alvo = f"{texto} {nome_arquivo}"

    tipo: TipoDocumento | None = None
    pontos = 0
    if _PPC.search(alvo):
        tipo, pontos = TipoDocumento.PPC, 5
    elif _EMENTARIO.search(alvo):
        tipo, pontos = TipoDocumento.EMENTARIO, 4
    elif _MATRIZ.search(alvo):
        tipo, pontos = TipoDocumento.MATRIZ, 4
    if _NEGATIVO.search(alvo):
        pontos -= 10
    if url.lower().split("?")[0].endswith(".pdf"):
        pontos += 1
    return tipo, pontos


def encontrar_links_ppc(html: str, base_url: str, *, limiar: int = LIMIAR) -> list[LinkCandidato]:
    """Links e iframes que apontam para PDF/Drive e parecem PPC, matriz ou ementário."""
    soup = BeautifulSoup(html, "lxml")
    melhores: dict[str, LinkCandidato] = {}

    for tag in soup.find_all(["a", "iframe"]):
        # O Google Sites coloca a URL do iframe em data-src
        bruto = tag.get("href") if tag.name == "a" else (tag.get("src") or tag.get("data-src"))
        if not bruto:
            continue
        url = desembrulhar_redirect_google(urljoin(base_url, str(bruto)))
        if not _parece_documento(url):
            continue
        rotulo = _rotulo(tag)
        tipo, pontos = classificar(rotulo, url)
        if tipo is None or pontos < limiar:
            continue
        drive_id = extrair_drive_id(url)
        chave = drive_id or url
        candidato = LinkCandidato(url, rotulo, tag.name, drive_id, tipo, pontos)
        atual = melhores.get(chave)
        # Mesmo arquivo linkado duas vezes ("Baixar" + nome): fica o rótulo mais informativo
        if atual is None or (pontos, len(rotulo)) > (atual.pontos, len(atual.texto)):
            melhores[chave] = candidato
    return list(melhores.values())
