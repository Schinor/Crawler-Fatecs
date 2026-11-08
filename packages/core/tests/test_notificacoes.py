"""Quando uma versão gera aviso e como o e-mail sai (SMTP simulado)."""

import smtplib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select

from fatecorg_core import notificacoes
from fatecorg_core.db import Base, NotificacaoDB, sessao
from fatecorg_core.domain import PPCEncontrado, Unidade
from fatecorg_core.notificacoes import NotificacaoSettings, despachar_pendentes
from fatecorg_core.repositories import CatalogoRepo, VersaoRepo

BASE = datetime(2026, 11, 1, 3, tzinfo=UTC)
URL = "https://fatec.br/matriz.pdf"
POMPEIA = Unidade.model_validate(
    {
        "slug": "pompeia", "nome": "Fatec", "cidade": "Pompeia", "site_url": "https://fatec.br",
        "plataforma": "google_sites",
        "cursos": [{"slug": "ads", "nome": "ADS", "url": "https://fatec.br/ads"}],
    }
)  # fmt: skip
SMTP_OK = {"smtp_host": "smtp.teste.invalid", "destinatarios": "r@teste.invalid"}


@pytest.fixture
def engine():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessao(engine) as s:
        CatalogoRepo(s).sincronizar([POMPEIA])
    return engine


def ppc(n: int, url: str | None = URL, tipo: str = "matriz") -> PPCEncontrado:
    sha = f"{n:x}" * 64
    return PPCEncontrado.model_validate(
        {
            "unidade_slug": "pompeia", "curso_slug": "ads", "curso_nome": "ADS",
            "tipo_documento": tipo, "pagina_url": "https://fatec.br/ads", "arquivo_url": url,
            "titulo_link": f"Matriz {n}", "sha256": sha[:64], "caminho_local": f"x/{n}.pdf",
            "tamanho_bytes": 10, "coletado_em": BASE + timedelta(days=n),
        }
    )  # fmt: skip


def registrar(engine, n, texto, **kw) -> PPCEncontrado:
    notificar = kw.pop("notificar", True)
    with sessao(engine) as s:
        return VersaoRepo(s).registrar(ppc(n, **kw), texto, notificar=notificar)


def linhas(engine):
    with sessao(engine) as s:
        return list(s.scalars(select(NotificacaoDB).order_by(NotificacaoDB.id)))


def settings(**extra) -> NotificacaoSettings:
    return NotificacaoSettings(_env_file=None, **(SMTP_OK | extra))  # type: ignore[call-arg]


class SmtpFalso:
    enviados: list = []
    tls = False
    falhar = False

    def __init__(self, host, porta, timeout):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        SmtpFalso.tls = True

    def send_message(self, msg):
        if SmtpFalso.falhar:
            raise smtplib.SMTPServerDisconnected("detalhe interno do servidor")
        SmtpFalso.enviados.append(msg)


@pytest.fixture(autouse=True)
def smtp(monkeypatch):
    SmtpFalso.enviados, SmtpFalso.tls, SmtpFalso.falhar = [], False, False
    monkeypatch.setattr(notificacoes.smtplib, "SMTP", SmtpFalso)
    return SmtpFalso


def test_primeira_versao_gera_aviso_de_documento_novo(engine):
    assert registrar(engine, 1, "texto").so_arquivo_mudou is False
    assert [n.documento_novo for n in linhas(engine)] == [True]


def test_texto_diferente_gera_aviso_de_nova_versao(engine):
    registrar(engine, 1, "texto antigo")
    registrar(engine, 2, "texto novo")
    assert [n.documento_novo for n in linhas(engine)] == [True, False]


def test_so_o_arquivo_mudou_nao_gera_aviso(engine):
    registrar(engine, 1, "mesmo   texto\ncom quebras")
    assert registrar(engine, 2, "mesmo texto com\n\nquebras").so_arquivo_mudou is True
    assert len(linhas(engine)) == 1
    with sessao(engine) as s:
        assert VersaoRepo(s).listar()[0].so_arquivo_mudou is True


def test_compara_com_a_anterior_do_mesmo_documento(engine):
    registrar(engine, 1, "igual", url="https://fatec.br/a.pdf")
    registrar(engine, 2, "igual", url="https://fatec.br/b.pdf")  # outro link, outro documento
    registrar(engine, 3, "igual", url=None)  # upload é sempre um documento próprio
    registrar(engine, 4, "igual", url=None)
    assert [n.documento_novo for n in linhas(engine)] == [True, True, True, True]


@pytest.mark.parametrize("texto", [None, "", "   "])
def test_sem_texto_nao_da_para_afirmar_que_nao_mudou(engine, texto):
    registrar(engine, 1, texto)
    assert registrar(engine, 2, texto).so_arquivo_mudou is False
    assert len(linhas(engine)) == 2


def test_importacao_nao_gera_aviso(engine):
    registrar(engine, 1, "texto", notificar=False)
    assert linhas(engine) == []


def test_varias_versoes_saem_num_email_so_e_uma_vez(engine, smtp):
    registrar(engine, 1, "a")
    registrar(engine, 2, "b")
    assert despachar_pendentes(engine, settings()).enviadas == 2
    assert len(smtp.enviados) == 1
    corpo = smtp.enviados[0].get_content()
    assert "Documento novo" in corpo and "Nova versão" in corpo and URL in corpo
    assert smtp.tls is True
    assert despachar_pendentes(engine, settings()).enviadas == 0
    assert len(smtp.enviados) == 1


def test_falha_de_smtp_guarda_o_erro_e_tenta_de_novo(engine, smtp):
    registrar(engine, 1, "a")
    smtp.falhar = True
    assert despachar_pendentes(engine, settings()).erro == "SMTPServerDisconnected"
    assert linhas(engine)[0].erro == "SMTPServerDisconnected"
    assert linhas(engine)[0].enviada_em is None
    smtp.falhar = False
    assert despachar_pendentes(engine, settings()).enviadas == 1
    assert linhas(engine)[0].erro is None


def test_sem_smtp_a_versao_fica_pendente(engine, smtp):
    registrar(engine, 1, "a")
    sem = NotificacaoSettings(_env_file=None)  # type: ignore[call-arg]
    assert despachar_pendentes(engine, sem).enviadas == 0
    assert smtp.enviados == []
    assert linhas(engine)[0].enviada_em is None


def test_tls_so_e_dispensado_quando_pedido(engine, smtp):
    registrar(engine, 1, "a")
    despachar_pendentes(engine, settings(smtp_tls=False))
    assert smtp.tls is False


def test_email_limita_a_quantidade_e_deixa_o_resto_para_o_proximo(engine, smtp, monkeypatch):
    monkeypatch.setattr(notificacoes, "MAX_VERSOES_POR_EMAIL", 1)
    registrar(engine, 1, "a")
    registrar(engine, 2, "b")
    assert despachar_pendentes(engine, settings()).enviadas == 1
    assert despachar_pendentes(engine, settings()).enviadas == 1
    assert len(smtp.enviados) == 2
