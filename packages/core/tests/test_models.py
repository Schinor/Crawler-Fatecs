from datetime import UTC, datetime

from pydantic import HttpUrl

from fatecorg_core.domain import (
    Coleta,
    PPCEncontrado,
    StatusColeta,
    TipoDocumento,
    Unidade,
)


def test_ppc_encontrado_valida_urls_e_tem_tipo_padrao_ppc():
    ppc = PPCEncontrado(
        unidade_slug="pompeia",
        curso_slug="sistemas-inteligentes",
        curso_nome="Sistemas Inteligentes",
        pagina_url=HttpUrl("https://www.fatecpompeia.edu.br/sistemas-inteligentes"),
        arquivo_url=HttpUrl("https://drive.google.com/uc?export=download&id=abc"),
        titulo_link="PPC CST Sistemas Inteligentes",
        sha256="0" * 64,
        caminho_local="ppcs/pompeia/sistemas-inteligentes/x.pdf",
        tamanho_bytes=1024,
        coletado_em=datetime.now(UTC),
    )
    assert ppc.tipo_documento is TipoDocumento.PPC
    assert PPCEncontrado.model_validate_json(ppc.model_dump_json()) == ppc


def test_unidade_aceita_cursos_do_seed():
    unidade = Unidade.model_validate(
        {
            "slug": "marilia",
            "nome": "Fatec Marília",
            "cidade": "Marília",
            "site_url": "https://fatecmarilia.cps.sp.gov.br",
            "plataforma": "wordpress",
            "cursos": [
                {
                    "slug": "alimentos",
                    "nome": "Alimentos",
                    "url": "https://fatecmarilia.cps.sp.gov.br/tecnologia-em-alimentos/",
                }
            ],
        }
    )
    assert unidade.cursos[0].slug == "alimentos"


def test_coleta_serializa_status():
    coleta = Coleta(
        unidade_slug="pompeia",
        curso_slug="map",
        curso_nome="MAP",
        iniciada_em=datetime.now(UTC),
        status=StatusColeta.SEM_PPC,
    )
    assert '"status":"sem_ppc"' in coleta.model_dump_json()
