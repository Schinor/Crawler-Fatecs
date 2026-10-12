"""Adaptadores por plataforma (Google Sites, genérico/WordPress)."""

from fatecorg_core.domain import Plataforma
from fatecorg_crawler.sources.base import Adaptador, PaginaCurso
from fatecorg_crawler.sources.generico import Generico
from fatecorg_crawler.sources.google_sites import GoogleSites

__all__ = ["Adaptador", "PaginaCurso", "adaptador_para"]


def adaptador_para(plataforma: Plataforma) -> Adaptador:
    if plataforma is Plataforma.GOOGLE_SITES:
        return GoogleSites()
    return Generico()  # WordPress do CPS funciona com o genérico (ver docs/inventario-sites.md)
