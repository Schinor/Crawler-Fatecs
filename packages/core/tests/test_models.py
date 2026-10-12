from datetime import UTC, datetime

from fatecorg_core.domain import PPCEncontrado


def test_ppc_encontrado_valida_urls():
    ppc = PPCEncontrado(
        unidade_slug="pompeia",
        curso_nome="Sistemas Inteligentes",
        pagina_url="https://www.fatecpompeia.edu.br/sistemas-inteligentes",
        arquivo_url="https://drive.google.com/uc?export=download&id=abc",
        titulo_link="PPC CST Sistemas Inteligentes",
        sha256="0" * 64,
        caminho_local="data/ppcs/pompeia/x.pdf",
        tamanho_bytes=1024,
        coletado_em=datetime.now(UTC),
    )
    assert ppc.unidade_slug == "pompeia"
