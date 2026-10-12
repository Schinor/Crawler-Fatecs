"""Integração real com os sites. Não roda no CI: uv run pytest -m rede"""

import pytest

from fatecorg_core.domain import TipoDocumento
from fatecorg_crawler.config import CrawlerSettings
from fatecorg_crawler.discover import encontrar_links_ppc
from fatecorg_crawler.fetch import Fetcher

pytestmark = pytest.mark.rede


@pytest.mark.parametrize(
    ("url", "tipo"),
    [
        ("https://www.fatecpompeia.edu.br/sistemas-inteligentes", TipoDocumento.PPC),
        ("https://fatecmarilia.cps.sp.gov.br/gestao-comercial/", TipoDocumento.MATRIZ),
    ],
)
def test_pagina_real_ainda_publica_documento(url, tipo, tmp_path):
    with Fetcher(CrawlerSettings(data_dir=tmp_path)) as f:
        resp = f.get(url, salvar_raw=False)
    tipos = {c.tipo for c in encontrar_links_ppc(resp.texto(), resp.url)}
    assert tipo in tipos
