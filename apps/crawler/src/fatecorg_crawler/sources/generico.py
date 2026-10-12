"""Adaptador genérico (WordPress e demais): cursos do seed ou BFS limitada no mesmo domínio."""

from collections import deque
from urllib.parse import urljoin, urlsplit

import httpx
from bs4 import BeautifulSoup

from fatecorg_core.domain import Plataforma, Unidade
from fatecorg_crawler.fetch import BloqueadoPorRobots, Fetcher
from fatecorg_crawler.sources.base import PaginaCurso, paginas_do_seed, parece_curso, slugificar

PRIORIDADE = ("curso", "cst", "graduacao", "tecnologia")
MAX_PAGINAS = 60  # teto de páginas por unidade: coleta dirigida, não espelho do site


class Generico:
    plataforma = Plataforma.GENERICO

    def paginas_de_curso(self, unidade: Unidade, fetcher: Fetcher) -> list[PaginaCurso]:
        if unidade.cursos:
            return paginas_do_seed(unidade)
        return bfs_cursos(str(unidade.site_url), unidade.slug, fetcher, fetcher.settings.max_depth)


def bfs_cursos(home: str, unidade_slug: str, fetcher: Fetcher, max_depth: int) -> list[PaginaCurso]:
    host = urlsplit(home).netloc
    fila: deque[tuple[str, int]] = deque([(home, 0)])
    visitadas: set[str] = set()
    achadas: dict[str, PaginaCurso] = {}
    while fila and len(visitadas) < MAX_PAGINAS:
        url, profundidade = fila.popleft()
        if url in visitadas:
            continue
        visitadas.add(url)
        try:
            resp = fetcher.get(url, unidade=unidade_slug)
        except (BloqueadoPorRobots, httpx.HTTPError):
            continue
        if not resp.ok or "html" not in resp.content_type:
            continue
        proximos: list[tuple[str, int]] = []
        for a in BeautifulSoup(resp.texto(), "lxml").find_all("a", href=True):
            destino = urljoin(url, str(a["href"])).split("#")[0]
            if urlsplit(destino).netloc != host or destino in visitadas:
                continue
            texto = a.get_text(" ", strip=True)
            if texto and parece_curso(texto) and destino not in achadas:
                achadas[destino] = PaginaCurso(slugificar(texto), texto, destino)
            if profundidade + 1 <= max_depth:
                prioridade = 0 if any(p in destino.lower() for p in PRIORIDADE) else 1
                proximos.append((destino, prioridade))
        for destino, _ in sorted(proximos, key=lambda x: x[1]):
            fila.append((destino, profundidade + 1))
    return list(achadas.values())
