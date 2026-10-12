"""Extrai e normaliza o texto de PDFs com PyMuPDF."""

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pymupdf


@dataclass
class TextoExtraido:
    texto: str
    paginas: int
    precisa_ocr: bool


def normalizar_texto(texto: str) -> str:
    """Versão estável do texto para comparar versões: junta hifenização, colapsa espaços."""
    texto = unicodedata.normalize("NFC", texto).replace("­", "")  # hífen invisível
    texto = re.sub(r"(\w)-\n(\w)", r"\1\2", texto)  # palavra quebrada no fim da linha
    linhas = (re.sub(r"[ \t ]+", " ", linha).strip() for linha in texto.splitlines())
    texto = "\n".join(linhas)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def extrair_texto(caminho_pdf: Path, *, min_chars: int = 500) -> TextoExtraido:
    with pymupdf.open(caminho_pdf) as doc:
        bruto = "\n".join(pagina.get_text() for pagina in doc)  # type: ignore[attr-defined]
        paginas = doc.page_count
    texto = normalizar_texto(bruto)
    return TextoExtraido(texto=texto, paginas=paginas, precisa_ocr=len(texto) < min_chars)
