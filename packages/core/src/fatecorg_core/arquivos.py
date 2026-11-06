"""Arquivos de documentos: formato pela assinatura, chave no storage e texto dos PDFs.

Compartilhado pelo crawler e pelo upload manual da API, para que os dois gravem igual.
"""

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf

TIPOS_MIME = {
    "pdf": "application/pdf",
    "doc": "application/msword",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "odt": "application/vnd.oasis.opendocument.text",
    "zip": "application/zip",
}


def detectar_formato(conteudo: bytes) -> str | None:
    """Formato pelo conteúdo (assinatura), não pela extensão. None = não é documento."""
    if conteudo.startswith(b"%PDF"):
        return "pdf"
    if conteudo.startswith(b"\xd0\xcf\x11\xe0"):
        return "doc"
    if conteudo.startswith(b"PK\x03\x04"):
        try:
            nomes = zipfile.ZipFile(io.BytesIO(conteudo)).namelist()
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in nomes:
            return "docx"
        if "content.xml" in nomes and "mimetype" in nomes:
            return "odt"
        return "zip"
    return None


def chave_arquivo(unidade_slug: str, curso_slug: str, sha256: str, formato: str) -> str:
    """Mesma chave em data/ e no Garage."""
    return f"ppcs/{unidade_slug}/{curso_slug}/{sha256}.{formato}"


def chave_texto(chave: str) -> str:
    return chave.rsplit(".", 1)[0] + ".txt"


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


def extrair_texto(pdf: Path | bytes, *, min_chars: int = 500) -> TextoExtraido:
    """Aceita o caminho ou o conteúdo do PDF (o RepoSink não grava o arquivo em disco)."""
    aberto = (
        pymupdf.open(stream=pdf, filetype="pdf") if isinstance(pdf, bytes) else pymupdf.open(pdf)
    )
    with aberto as doc:
        bruto = "\n".join(pagina.get_text() for pagina in doc)  # type: ignore[attr-defined]
        paginas = doc.page_count
    texto = normalizar_texto(bruto)
    return TextoExtraido(texto=texto, paginas=paginas, precisa_ocr=len(texto) < min_chars)
