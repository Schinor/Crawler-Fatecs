from datetime import UTC, datetime

from fatecorg_core.domain import Coleta, StatusColeta, TipoAviso
from fatecorg_core.notificacoes import NotificacaoSettings
from fatecorg_crawler.avisos import AvisoStore, montar_email

SEMANA_1 = datetime(2026, 10, 11, 3, tzinfo=UTC)
SEMANA_2 = datetime(2026, 10, 18, 3, tzinfo=UTC)
ROBOTS = "bloqueado pelo robots.txt: https://drive.google.com/uc?id=abc"


def coleta(status, quando, unidade="pompeia", curso="ads", **detalhe) -> Coleta:
    return Coleta(
        unidade_slug=unidade, curso_slug=curso, curso_nome=curso.upper(), iniciada_em=quando,
        status=status,
        detalhe={"pagina_url": f"https://{unidade}.br/{curso}", **detalhe},
    )  # fmt: skip


def drive_bloqueado(quando, **kw) -> Coleta:
    return coleta(
        StatusColeta.ERRO_DRIVE, quando, arquivo_url="https://drive.google.com/file/d/abc/view",
        tipo_documento="ppc", titulo_link="PPC ADS", erro=ROBOTS, **kw,
    )  # fmt: skip


def test_drive_bloqueado_abre_aviso_e_notifica_so_na_primeira_vez(tmp_path):
    store = AvisoStore(tmp_path)
    primeira = store.atualizar([drive_bloqueado(SEMANA_1)])
    assert len(primeira.novos) == 1
    assert primeira.novos[0].tipo is TipoAviso.DRIVE_BLOQUEADO

    segunda = store.atualizar([drive_bloqueado(SEMANA_2)])
    assert segunda.novos == []
    (aberto,) = store.ler()
    assert aberto.detectado_em == SEMANA_1
    assert aberto.visto_em == SEMANA_2


def test_outros_erros_do_drive_nao_viram_aviso(tmp_path):
    privado = coleta(
        StatusColeta.ERRO_DRIVE, SEMANA_1, arquivo_url="https://drive.google.com/x",
        erro="Drive devolveu HTML (privado ou removido)",
    )  # fmt: skip
    assert AvisoStore(tmp_path).atualizar([privado]).abertos == []


def test_aviso_fecha_quando_a_pagina_e_lida_e_o_problema_some(tmp_path):
    store = AvisoStore(tmp_path)
    store.atualizar([drive_bloqueado(SEMANA_1)])
    resultado = store.atualizar([coleta(StatusColeta.NOVO_PPC, SEMANA_2)])
    assert len(resultado.resolvidos) == 1
    assert store.ler() == []


def test_erro_de_rede_ou_outra_unidade_nao_fecham_aviso(tmp_path):
    store = AvisoStore(tmp_path)
    store.atualizar([drive_bloqueado(SEMANA_1)])
    store.atualizar([coleta(StatusColeta.ERRO_HTTP, SEMANA_2, erro="HTTP 503")])
    store.atualizar([coleta(StatusColeta.NOVO_PPC, SEMANA_2, unidade="marilia")])
    assert len(store.ler()) == 1


def test_email_cita_todas_as_unidades_e_pede_solucao_quando_ha_mais_de_uma(tmp_path):
    novos = (
        AvisoStore(tmp_path)
        .atualizar([drive_bloqueado(SEMANA_1), drive_bloqueado(SEMANA_1, unidade="garca")])
        .novos
    )
    assunto, corpo = montar_email(novos, SEMANA_1)
    assert "garca, pompeia" in assunto
    assert "mapear uma solução" in corpo


def test_email_so_e_enviado_com_smtp_configurado():
    sem_smtp = NotificacaoSettings(_env_file=None, destinatarios="a@x.br")  # type: ignore[call-arg]
    assert not sem_smtp.email_configurado
    com_smtp = NotificacaoSettings(
        _env_file=None,  # type: ignore[call-arg]
        destinatarios="a@x.br, b@x.br",
        smtp_host="smtp.x.br",
    )
    assert com_smtp.email_configurado
    assert com_smtp.lista_destinatarios == ["a@x.br", "b@x.br"]
