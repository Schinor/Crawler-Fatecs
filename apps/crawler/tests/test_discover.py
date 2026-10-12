from fatecorg_crawler.discover import encontrar_links_ppc
from fatecorg_crawler.drive import extrair_drive_id, url_download_direto

HTML_GOOGLE_SITES = """
<html><body>
  <a href="/secretaria/ementa">Ementa</a>
  <a href="https://drive.google.com/file/d/1XyZ0123456789ab/view">Deliberação 106</a>
  <iframe title="PPC CST Sistemas Inteligentes - Fatec Pompeia.pdf"
          src="https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/preview"></iframe>
  <a href="/docs/Projeto_Pedagogico_BigData.pdf">Projeto Pedagógico do Curso</a>
</body></html>
"""


def test_extrai_id_do_drive():
    assert extrair_drive_id("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/preview") == (
        "1AbCdEfGhIjKlMnOpQrStUv"
    )
    assert extrair_drive_id("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQrStUv") == (
        "1AbCdEfGhIjKlMnOpQrStUv"
    )
    assert extrair_drive_id("https://www.fatecpompeia.edu.br/map") is None


def test_url_download_direto():
    assert url_download_direto("abc123def456").endswith("id=abc123def456")


def test_encontra_iframe_do_drive_e_pdf_ignorando_outros_documentos():
    links = encontrar_links_ppc(HTML_GOOGLE_SITES, "https://www.fatecpompeia.edu.br/x")
    urls = {link.url for link in links}
    assert "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/preview" in urls
    assert "https://www.fatecpompeia.edu.br/docs/Projeto_Pedagogico_BigData.pdf" in urls
    assert len(links) == 2  # a Deliberação 106 fica de fora
