import pytest
from fastapi.testclient import TestClient

from fatecorg_api.config import ApiSettings
from fatecorg_api.main import create_app
from fatecorg_core import notificacoes
from fatecorg_core.notificacoes import NotificacaoSettings


@pytest.fixture
def enviar(auth):
    def _enviar(cliente, conteudo: bytes, headers=None, **form):
        return _post(cliente, conteudo, auth if headers is None else headers, **form)

    return _enviar


def _post(cliente, conteudo: bytes, headers, **form):
    dados = {"unidade": "pompeia", "curso": "big-data", "tipo_documento": "ppc", **form}
    return cliente.post(
        "/ppcs", data=dados, files={"arquivo": ("ppc.pdf", conteudo)}, headers=headers
    )


def test_upload_desligado_sem_segredo_configurado(fazer_cliente, enviar, fazer_pdf):
    assert enviar(fazer_cliente(jwt_segredo=""), fazer_pdf()).status_code == 503


def test_upload_exige_token_valido(cliente, enviar, fazer_pdf):
    assert enviar(cliente, fazer_pdf(), headers={}).status_code == 401
    assert (
        enviar(cliente, fazer_pdf(), headers={"Authorization": "Bearer errado"}).status_code == 401
    )


def test_upload_grava_versao_extrai_texto_e_fecha_o_aviso(cliente, storage, enviar, fazer_pdf):
    assert len(cliente.get("/avisos").json()) == 1
    resp = enviar(cliente, fazer_pdf(), titulo="PPC Big Data 2024")
    assert resp.status_code == 201, resp.text
    versao = resp.json()
    assert versao["origem"] == "upload"
    assert versao["arquivo_url"] is None
    assert versao["paginas"] == 1
    assert "Projeto Pedagógico" in cliente.get(versao["links"]["texto"]).text
    assert cliente.get("/avisos").json() == []  # o PPC bloqueado no Drive chegou


def test_mesmo_arquivo_duas_vezes_da_conflito(cliente, enviar, fazer_pdf):
    conteudo = fazer_pdf()
    assert enviar(cliente, conteudo).status_code == 201
    assert enviar(cliente, conteudo).status_code == 409


def test_upload_recusa_o_que_nao_e_documento(cliente, enviar, fazer_pdf):
    resp = enviar(cliente, b"<script>alert(1)</script>")
    assert resp.status_code == 415


def test_upload_recusa_arquivo_grande(fazer_cliente, enviar, fazer_pdf):
    cliente = fazer_cliente(max_upload_mb=1)
    assert enviar(cliente, b"%PDF" + b"0" * (1024 * 1024)).status_code == 413


def test_upload_recusa_curso_inexistente_e_slug_malicioso(cliente, enviar, fazer_pdf):
    assert enviar(cliente, fazer_pdf(), curso="medicina").status_code == 404
    assert enviar(cliente, fazer_pdf(), curso="../../etc").status_code == 422


def test_upload_de_conteudo_novo_manda_o_email_depois_de_gravar(
    engine, storage, auth, fazer_pdf, monkeypatch
):
    """A tarefa em segundo plano precisa achar a fila já gravada no banco."""
    enviados = []
    monkeypatch.setattr(notificacoes, "enviar_email", lambda _c, a, c: enviados.append((a, c)))
    config = NotificacaoSettings(
        _env_file=None,  # type: ignore[call-arg]
        smtp_host="smtp.teste.invalid",
        destinatarios="r@teste.invalid",
    )
    settings = ApiSettings(_env_file=None, jwt_segredo="segredo-de-teste-" + "x" * 32)  # type: ignore[call-arg]
    cliente = TestClient(
        create_app(engine=engine, storage=storage, settings=settings, notificacao=config)
    )
    resp = _post(cliente, fazer_pdf(), auth, titulo="PPC 2024")
    assert resp.status_code == 201, resp.text
    assert resp.json()["so_arquivo_mudou"] is False
    assert len(enviados) == 1
    assert "PPC 2024" in enviados[0][1] and "enviado manualmente" in enviados[0][1]
