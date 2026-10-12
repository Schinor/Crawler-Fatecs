import pytest

from fatecorg_core.domain import TipoDocumento
from fatecorg_crawler.discover import classificar, encontrar_links_ppc
from fatecorg_crawler.drive import (
    desembrulhar_redirect_google,
    extrair_drive_id,
    url_download_direto,
)

HTML_GOOGLE_SITES = """
<html><body>
  <a href="/secretaria/ementa">Ementa</a>
  <a href="https://drive.google.com/file/d/1XyZ0123456789ab/view">Deliberação 106</a>
  <a href="https://drive.google.com/file/d/1TsiProva0123456/view">TSI prova</a>
  <iframe aria-label="Drive, PPC CST Sistemas Inteligentes - Fatec Pompeia.pdf"
          data-src="https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/preview"></iframe>
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


def test_desembrulha_redirect_do_google_sites():
    url = "https://www.google.com/url?q=https%3A%2F%2Fwww.fatecpompeia.edu.br%2Fbigdata&sa=D"
    assert desembrulhar_redirect_google(url) == "https://www.fatecpompeia.edu.br/bigdata"
    assert desembrulhar_redirect_google("https://x.br/a") == "https://x.br/a"


def test_iframe_com_data_src_e_aria_label_e_ignora_outros_documentos():
    links = encontrar_links_ppc(HTML_GOOGLE_SITES, "https://www.fatecpompeia.edu.br/x")
    urls = {link.url for link in links}
    assert urls == {
        "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/preview",
        "https://www.fatecpompeia.edu.br/docs/Projeto_Pedagogico_BigData.pdf",
    }
    assert all(link.tipo is TipoDocumento.PPC for link in links)


@pytest.mark.parametrize(
    ("rotulo", "url", "tipo"),
    [
        ("Grade C31 – 2014-2 até atual", "https://b.net/Grade-C31.pdf", TipoDocumento.MATRIZ),
        ("Baixar", "https://b.net/MATRIZ-GCOM-M75.pdf", TipoDocumento.MATRIZ),
        ("EMENTAS GRADE A31", "https://b.net/EMENTAS-GRADE-A31.zip", TipoDocumento.EMENTARIO),
        ("EMENTÁRIO GC – C75", "https://b.net/x.pdf", TipoDocumento.EMENTARIO),
        ("PPC do curso", "https://drive.google.com/file/d/abcdefghijkl/view", TipoDocumento.PPC),
    ],
)
def test_classifica_tipo_de_documento(rotulo, url, tipo):
    achado, pontos = classificar(rotulo, url)
    assert achado is tipo
    assert pontos >= 4


@pytest.mark.parametrize(
    "rotulo",
    ["ALIMENTOS – HORÁRIO DE AULAS 2026-2", "REDEPS – Regulamento Disciplinar", "Calendário 2026"],
)
def test_penaliza_documentos_que_nao_sao_curriculares(rotulo):
    _, pontos = classificar(rotulo, "https://b.net/arquivo.pdf")
    assert pontos < 4


def test_mesmo_arquivo_linkado_duas_vezes_fica_com_o_melhor_rotulo():
    html = """
      <a href="https://b.net/Grade-B31.pdf">Baixar</a>
      <a href="https://b.net/Grade-B31.pdf">Grade B31 – 2009-2 até 2014-1</a>
    """
    (link,) = encontrar_links_ppc(html, "https://fatecmarilia.cps.sp.gov.br/x/")
    assert link.texto == "Grade B31 – 2009-2 até 2014-1"


# ---------------------------------------------------------------- snapshots reais (12/10/2026)


def test_snapshot_pompeia_sistemas_inteligentes_acha_o_ppc_no_iframe(ler_fixture):
    html = ler_fixture("pompeia_sistemas-inteligentes.html")
    (link,) = encontrar_links_ppc(html, "https://www.fatecpompeia.edu.br/sistemas-inteligentes")
    assert link.tipo is TipoDocumento.PPC
    assert link.origem == "iframe"
    assert link.drive_id == "11hRGyeWirp0X41BRvVk2rCHlIHZE98nN"
    assert "PPC CST Sistemas Inteligentes" in link.texto


def test_snapshot_pompeia_map_nao_tem_ppc(ler_fixture):
    html = ler_fixture("pompeia_map.html")
    assert encontrar_links_ppc(html, "https://www.fatecpompeia.edu.br/map") == []


def test_snapshot_marilia_alimentos_tem_tres_grades_e_tres_ementarios(ler_fixture):
    html = ler_fixture("marilia_alimentos.html")
    links = encontrar_links_ppc(html, "https://fatecmarilia.cps.sp.gov.br/tecnologia-em-alimentos/")
    tipos = sorted(link.tipo.value for link in links)
    assert tipos == ["ementario"] * 3 + ["matriz"] * 3
    assert not any("HORARIO" in link.url.upper() for link in links)


def test_snapshot_marilia_gestao_comercial(ler_fixture):
    html = ler_fixture("marilia_gestao-comercial.html")
    links = encontrar_links_ppc(html, "https://fatecmarilia.cps.sp.gov.br/gestao-comercial/")
    assert sorted(link.tipo.value for link in links) == [
        "ementario",
        "ementario",
        "matriz",
        "matriz",
    ]
