"""Encontra links de PPC numa página HTML, sem seletor específico por site."""

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from bd_ppcs_crawler.drive import extrair_drive_id

PADRAO_PPC = re.compile(
    r"\bppc\b|projeto\s+pedag[oó]gico|plano\s+pedag[oó]gico|matriz\s+curricular",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LinkCandidato:
    url: str
    texto: str
    origem: str  # "a" (link) ou "iframe"
    drive_id: str | None


def _parece_documento(url: str) -> bool:
    return url.lower().split("?")[0].endswith(".pdf") or extrair_drive_id(url) is not None


def encontrar_links_ppc(html: str, base_url: str) -> list[LinkCandidato]:
    """Links e iframes cujo texto, title ou URL mencionem PPC e apontem para PDF ou Drive."""
    soup = BeautifulSoup(html, "lxml")
    vistos: set[str] = set()
    achados: list[LinkCandidato] = []

    for tag in soup.find_all(["a", "iframe"]):
        bruto = tag.get("href") if tag.name == "a" else tag.get("src")
        if not bruto:
            continue
        url = urljoin(base_url, str(bruto))
        partes = [
            tag.get_text(" ", strip=True),
            str(tag.get("title") or ""),
            str(tag.get("aria-label") or ""),
        ]
        rotulo = " ".join(p for p in partes if p)
        menciona_ppc = bool(PADRAO_PPC.search(rotulo) or PADRAO_PPC.search(url))
        if menciona_ppc and _parece_documento(url) and url not in vistos:
            vistos.add(url)
            achados.append(LinkCandidato(url, rotulo, tag.name, extrair_drive_id(url)))
    return achados
