"""Entidades do domínio. Este arquivo é o contrato entre crawler, API e banco."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, HttpUrl


class Plataforma(StrEnum):
    GOOGLE_SITES = "google_sites"
    WORDPRESS = "wordpress"
    GENERICO = "generico"


class Unidade(BaseModel):
    slug: str
    nome: str
    cidade: str
    site_url: HttpUrl
    plataforma: Plataforma
    paginas_cursos: list[HttpUrl] = []
    ativa: bool = True


class PPCEncontrado(BaseModel):
    """Saída do crawler para cada PPC baixado (uma linha do JSONL)."""

    unidade_slug: str
    curso_nome: str
    pagina_url: HttpUrl
    arquivo_url: HttpUrl
    titulo_link: str
    sha256: str
    caminho_local: str
    tamanho_bytes: int
    coletado_em: datetime
