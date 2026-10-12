"""Contrato dos adaptadores: dada uma unidade, quais páginas de curso visitar."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from fatecorg_core.domain import Plataforma, Unidade
from fatecorg_crawler.fetch import Fetcher

# Nomes que indicam página de curso de graduação tecnológica
PADRAO_CURSO = re.compile(
    r"\bcst\b|curso|gradua|tecnologia em|sistemas|gestao|analise|desenvolvimento|alimentos"
    r"|agronegocio|big ?data|mecanizacao|logistica|comercio|eventos|automacao|mecatronica",
)


@dataclass(frozen=True)
class PaginaCurso:
    curso_slug: str
    curso_nome: str
    url: str


class Adaptador(Protocol):
    plataforma: Plataforma

    def paginas_de_curso(self, unidade: Unidade, fetcher: Fetcher) -> list[PaginaCurso]: ...


def paginas_do_seed(unidade: Unidade) -> list[PaginaCurso]:
    return [PaginaCurso(c.slug, c.nome, str(c.url)) for c in unidade.cursos]


def slugificar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", sem_acento.lower()).strip("-")


def parece_curso(texto: str) -> bool:
    return bool(PADRAO_CURSO.search(slugificar(texto).replace("-", " ")))
