"""Utilitários para links do Google Drive (Google Sites incorpora PPCs como arquivos do Drive)."""

import re

_PADROES_ID = (
    re.compile(r"drive\.google\.com/file/d/([\w-]{10,})"),
    re.compile(r"drive\.google\.com/(?:open|uc)\?(?:.*&)?id=([\w-]{10,})"),
    re.compile(r"docs\.google\.com/(?:document|presentation|spreadsheets)/d/([\w-]{10,})"),
)


def extrair_drive_id(url: str) -> str | None:
    """Devolve o ID do arquivo do Drive presente na URL, ou None."""
    for padrao in _PADROES_ID:
        if m := padrao.search(url):
            return m.group(1)
    return None


def url_download_direto(drive_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={drive_id}"
