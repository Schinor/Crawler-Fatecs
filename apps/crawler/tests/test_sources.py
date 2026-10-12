from fatecorg_crawler.sources.base import parece_curso, slugificar
from fatecorg_crawler.sources.google_sites import paginas_do_menu


def test_menu_do_google_sites_deduplica_e_desembrulha():
    html = """
    <nav>
      <a href="/sistemas-inteligentes">Sistemas Inteligentes</a>
      <a href="https://www.google.com/url?q=https%3A%2F%2Fwww.fatecpompeia.edu.br%2Fbigdata&sa=D">
        Big Data no Agronegócio</a>
      <a href="/secretaria/ementa">Secretaria</a>
    </nav>
    <nav><a href="/sistemas-inteligentes">Sistemas Inteligentes</a></nav>
    """
    paginas = paginas_do_menu(html, "https://www.fatecpompeia.edu.br/")
    assert [p.url for p in paginas] == [
        "https://www.fatecpompeia.edu.br/sistemas-inteligentes",
        "https://www.fatecpompeia.edu.br/bigdata",
    ]


def test_slug_e_deteccao_de_curso():
    assert slugificar("CST em Gestão Comercial") == "cst-em-gestao-comercial"
    assert parece_curso("Tecnologia em Alimentos")
    assert not parece_curso("Biblioteca")
