"""Adaptador Google Sites (ex.: Fatec Pompeia).

Usa os cursos do seed. Sem seed, lê o menu da home: o Google Sites repete o menu várias vezes
no HTML e embrulha alguns links em google.com/url?q=..., por isso deduplicamos e desembrulhamos.
"""

from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from fatecorg_core.domain import Plataforma, Unidade
from fatecorg_crawler.drive import desembrulhar_redirect_google
from fatecorg_crawler.fetch import Fetcher
from fatecorg_crawler.sources.base import PaginaCurso, paginas_do_seed, parece_curso, slugificar


class GoogleSites:
    plataforma = Plataforma.GOOGLE_SITES

    def paginas_de_curso(self, unidade: Unidade, fetcher: Fetcher) -> list[PaginaCurso]:
        if unidade.cursos:
            return paginas_do_seed(unidade)
        home = str(unidade.site_url)
        resp = fetcher.get(home, unidade=unidade.slug)
        return paginas_do_menu(resp.texto(), home)


def paginas_do_menu(html: str, home: str) -> list[PaginaCurso]:
    host = urlsplit(home).netloc
    vistas: dict[str, PaginaCurso] = {}
    for a in BeautifulSoup(html, "lxml").select("nav a[href], [role=navigation] a[href]"):
        url = desembrulhar_redirect_google(urljoin(home, str(a["href"]))).split("#")[0]
        texto = a.get_text(" ", strip=True)
        if urlsplit(url).netloc != host or not texto or url in vistas:
            continue
        if parece_curso(texto):
            vistas[url] = PaginaCurso(slugificar(texto), texto, url)
    return list(vistas.values())
