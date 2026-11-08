"""Login, renovação, perfis e limites. Cookie e token de verdade, passando pela API inteira."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from fatecorg_api import cli as cli_api
from fatecorg_api.config import ApiSettings
from fatecorg_api.rotas.auth import COOKIE
from fatecorg_core.db import PPCVersaoDB, SessaoLoginDB, UnidadeDB, UsuarioDB, sessao
from fatecorg_core.domain import Perfil, Plataforma
from fatecorg_core.repositories import usuarios as repo_usuarios

EMAIL = "admin@teste.invalid"
SENHA = "senha-de-teste-longa"  # as mesmas do conftest
SEGREDO = "segredo-de-teste-" + "x" * 32


def entrar(cliente, email=EMAIL, senha=SENHA):
    return cliente.post("/auth/login", json={"email": email, "senha": senha})


def upload(cliente, conteudo, headers, unidade="pompeia", curso="big-data"):
    return cliente.post(
        "/ppcs",
        data={"unidade": unidade, "curso": curso, "tipo_documento": "ppc"},
        files={"arquivo": ("ppc.pdf", conteudo)},
        headers=headers,
    )


def bearer(resposta) -> dict[str, str]:
    return {"Authorization": f"Bearer {resposta.json()['access_token']}"}


def test_login_devolve_token_e_cookie_protegido(fazer_cliente, criar_usuario):
    criar_usuario()
    resp = entrar(fazer_cliente(cookie_seguro=True))
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["usuario"]["perfil"] == "admin_polo"
    assert "senha" not in resp.text and "hash" not in resp.text
    cookie = resp.headers["set-cookie"].lower()
    for atributo in ("httponly", "secure", "samesite=strict", "path=/auth"):
        assert atributo in cookie
    assert resp.headers["cache-control"] == "no-store"


def test_email_nao_diferencia_maiusculas(cliente, criar_usuario):
    criar_usuario()
    assert entrar(cliente, email=f"  {EMAIL.upper()} ").status_code == 200


def test_mesma_resposta_para_email_inexistente_e_senha_errada(cliente, criar_usuario):
    criar_usuario()
    inexistente, errada = entrar(cliente, email="x@teste.invalid"), entrar(cliente, senha="errada")
    assert inexistente.status_code == errada.status_code == 401
    assert inexistente.json() == errada.json()


def test_quinta_senha_errada_bloqueia_mesmo_com_a_senha_certa(cliente, criar_usuario, engine):
    criar_usuario()
    for _ in range(5):
        assert entrar(cliente, senha="errada").status_code == 401
    assert entrar(cliente).status_code == 401
    with sessao(engine) as s:
        conta = s.scalars(select(UsuarioDB)).one()
        assert conta.bloqueado_ate is not None
        conta.bloqueado_ate = datetime.now(UTC) - timedelta(seconds=1)
    assert entrar(cliente).status_code == 200


def test_acerto_zera_as_falhas(cliente, criar_usuario):
    criar_usuario()
    for _ in range(4):
        entrar(cliente, senha="errada")
    assert entrar(cliente).status_code == 200
    for _ in range(4):
        entrar(cliente, senha="errada")
    assert entrar(cliente).status_code == 200


def test_conta_desativada_nao_entra_e_perde_o_token(cliente, criar_usuario, engine, fazer_pdf):
    criar_usuario()
    resp = entrar(cliente)
    with sessao(engine) as s:
        s.scalars(select(UsuarioDB)).one().ativo = False
    assert entrar(cliente).status_code == 401
    assert upload(cliente, fazer_pdf(), bearer(resp)).status_code == 401
    assert cliente.post("/auth/refresh").status_code == 401


def test_login_desligado_sem_segredo(fazer_cliente):
    assert entrar(fazer_cliente(jwt_segredo="")).status_code == 503


def test_segredo_curto_impede_a_api_de_subir():
    with pytest.raises(ValueError, match="32"):
        ApiSettings(_env_file=None, jwt_segredo="curto")  # type: ignore[call-arg]


def test_refresh_sem_cookie_e_204(cliente):
    assert cliente.post("/auth/refresh").status_code == 204


def test_refresh_gira_o_cookie_e_guarda_so_o_hash(cliente, criar_usuario, engine):
    criar_usuario()
    entrar(cliente)
    primeiro = cliente.cookies[COOKIE]
    resp = cliente.post("/auth/refresh")
    assert resp.status_code == 200
    assert resp.json()["usuario"]["email"] == EMAIL
    assert cliente.cookies[COOKIE] != primeiro
    with sessao(engine) as s:
        guardados = list(s.scalars(select(SessaoLoginDB.token_sha256)))
    assert len(guardados) == 2
    assert primeiro not in guardados and cliente.cookies[COOKIE] not in guardados


def test_duas_abas_renovando_juntas_nao_derrubam_a_sessao(cliente, criar_usuario):
    criar_usuario()
    entrar(cliente)
    antigo = cliente.cookies[COOKIE]
    assert cliente.post("/auth/refresh").status_code == 200
    novo = cliente.cookies[COOKIE]
    cliente.cookies.clear()
    resp = cliente.post("/auth/refresh", cookies={COOKIE: antigo})
    assert resp.status_code == 200
    assert "set-cookie" not in resp.headers  # o cookie novo já está no navegador
    cliente.cookies.clear()
    assert cliente.post("/auth/refresh", cookies={COOKIE: novo}).status_code == 200


def test_token_ja_trocado_reapresentado_encerra_todas_as_sessoes(cliente, criar_usuario, engine):
    criar_usuario()
    entrar(cliente)
    roubado = cliente.cookies[COOKIE]
    cliente.post("/auth/refresh")
    legitimo = cliente.cookies[COOKIE]
    with sessao(engine) as s:
        for linha in s.scalars(select(SessaoLoginDB).where(SessaoLoginDB.girada_em.is_not(None))):
            linha.girada_em = datetime.now(UTC) - repo_usuarios.CARENCIA_GIRO * 2
    cliente.cookies.clear()
    assert cliente.post("/auth/refresh", cookies={COOKIE: roubado}).status_code == 401
    cliente.cookies.clear()
    assert cliente.post("/auth/refresh", cookies={COOKIE: legitimo}).status_code == 401


def test_refresh_vencido_e_recusado_e_o_cookie_apagado(cliente, criar_usuario, engine):
    criar_usuario()
    entrar(cliente)
    with sessao(engine) as s:
        s.scalars(select(SessaoLoginDB)).one().expira_em = datetime.now(UTC) - timedelta(seconds=1)
    resp = cliente.post("/auth/refresh")
    assert resp.status_code == 401
    assert (
        COOKIE in resp.headers["set-cookie"] and "max-age=0" in resp.headers["set-cookie"].lower()
    )


def test_renovar_apaga_as_sessoes_vencidas(cliente, criar_usuario, engine):
    criar_usuario()
    entrar(cliente)
    cliente.post("/auth/refresh")
    with sessao(engine) as s:
        girada = s.scalars(select(SessaoLoginDB).where(SessaoLoginDB.girada_em.is_not(None))).one()
        girada.expira_em = datetime.now(UTC) - timedelta(seconds=1)
    assert cliente.post("/auth/refresh").status_code == 200
    with sessao(engine) as s:
        assert len(list(s.scalars(select(SessaoLoginDB)))) == 2  # a atual e a girada agora


def test_logout_encerra_a_sessao(cliente, criar_usuario):
    criar_usuario()
    entrar(cliente)
    cookie = cliente.cookies[COOKIE]
    assert cliente.post("/auth/logout").status_code == 204
    cliente.cookies.clear()
    assert cliente.post("/auth/refresh", cookies={COOKIE: cookie}).status_code == 401


@pytest.mark.parametrize(
    "dados",
    [
        {"tipo": "acesso", "perfil": "admin_polo", "sub": "1", "exp": -60},  # vencido
        {"tipo": "refresh", "perfil": "admin_polo", "sub": "1", "exp": 60},  # outro tipo
        {"tipo": "acesso", "perfil": "reitor", "sub": "1", "exp": 60},  # perfil inexistente
        {"tipo": "acesso", "perfil": "admin_polo", "sub": "abc", "exp": 60},  # sub inválido
    ],
)
def test_upload_recusa_jwt_adulterado(cliente, criar_usuario, fazer_pdf, dados):
    criar_usuario()
    agora = datetime.now(UTC)
    token = jwt.encode(
        dados | {"iat": agora, "exp": agora + timedelta(seconds=dados["exp"])}, SEGREDO, "HS256"
    )
    assert upload(cliente, fazer_pdf(), {"Authorization": f"Bearer {token}"}).status_code == 401


def test_upload_recusa_jwt_de_outra_chave_e_sem_assinatura(cliente, criar_usuario, fazer_pdf):
    criar_usuario()
    agora = datetime.now(UTC)
    dados = {"tipo": "acesso", "perfil": "admin_polo", "sub": "1", "iat": agora,
             "exp": agora + timedelta(minutes=5)}  # fmt: skip
    for token in (
        jwt.encode(dados, "outra-chave-" + "y" * 32, "HS256"),
        jwt.encode(dados, "", "none"),
    ):
        assert upload(cliente, fazer_pdf(), {"Authorization": f"Bearer {token}"}).status_code == 401


def test_perfil_consulta_nao_envia_e_o_corpo_nem_e_lido(cliente, criar_usuario, cabecalho):
    class CorpoNaoLido:
        def __iter__(self):
            raise AssertionError("leu o corpo de quem não pode enviar")

    conta = criar_usuario(Perfil.CONSULTA)
    resp = cliente.post(
        "/ppcs",
        content=CorpoNaoLido(),
        headers=cabecalho(conta)
        | {"Content-Type": "multipart/form-data; boundary=x", "Content-Length": "300000000"},
    )
    assert resp.status_code == 403


def test_coordenador_envia_so_para_a_propria_unidade(
    cliente, criar_usuario, cabecalho, engine, fazer_pdf
):
    with sessao(engine) as s:
        s.add(
            UnidadeDB(
                slug="marilia", nome="Fatec Marília", cidade="Marília",
                site_url="https://exemplo.invalid", plataforma=Plataforma.WORDPRESS, ativa=True,
            )
        )  # fmt: skip
    daqui = cabecalho(criar_usuario(Perfil.COORDENADOR, "c1@teste.invalid", unidade="pompeia"))
    de_la = cabecalho(criar_usuario(Perfil.COORDENADOR, "c2@teste.invalid", unidade="marilia"))
    assert upload(cliente, fazer_pdf(), de_la).status_code == 403
    assert upload(cliente, fazer_pdf(), daqui).status_code == 201


def test_upload_registra_quem_enviou_sem_expor_na_api(
    cliente, criar_usuario, cabecalho, engine, fazer_pdf
):
    conta = criar_usuario()
    resp = upload(cliente, fazer_pdf(), cabecalho(conta))
    assert resp.status_code == 201
    assert "enviado_por" not in resp.text and conta.email not in resp.text
    with sessao(engine) as s:
        autor = s.scalar(
            select(PPCVersaoDB.enviado_por_id).where(PPCVersaoDB.sha256 == resp.json()["sha256"])
        )
    assert autor == conta.id


@pytest.fixture
def cli(engine, monkeypatch):
    monkeypatch.setattr(cli_api, "criar_engine", lambda: engine)
    return CliRunner()


CRIAR = ["criar-usuario", "--email", EMAIL, "--nome", "Pessoa", "--perfil", "admin_polo",
         "--senha-stdin"]  # fmt: skip


def test_cli_cria_a_conta_e_ela_entra(cli, cliente):
    r = cli.invoke(cli_api.app, CRIAR, input=f"{SENHA}\n")
    assert r.exit_code == 0, r.output
    assert SENHA not in r.output
    assert entrar(cliente).status_code == 200


def test_cli_recusa_senha_curta_email_repetido_e_coordenador_sem_unidade(cli):
    assert cli.invoke(cli_api.app, CRIAR, input="curta\n").exit_code == 1
    assert cli.invoke(cli_api.app, CRIAR, input=f"{SENHA}\n").exit_code == 0
    assert cli.invoke(cli_api.app, CRIAR, input=f"{SENHA}\n").exit_code == 1
    args = ["criar-usuario", "--email", "c@teste.invalid", "--nome", "C", "--perfil", "coordenador",
            "--senha-stdin"]  # fmt: skip
    assert cli.invoke(cli_api.app, args, input=f"{SENHA}\n").exit_code == 1


def test_cli_redefinir_senha_derruba_sessoes_e_desbloqueia(cli, cliente, criar_usuario, engine):
    criar_usuario()
    entrar(cliente)
    with sessao(engine) as s:
        s.scalars(select(UsuarioDB)).one().bloqueado_ate = datetime.now(UTC) + timedelta(hours=1)
    nova = "outra-senha-bem-longa"
    args = ["redefinir-senha", "--email", EMAIL, "--senha-stdin"]
    assert cli.invoke(cli_api.app, args, input=f"{nova}\n").exit_code == 0
    assert cliente.post("/auth/refresh").status_code == 401
    assert entrar(cliente).status_code == 401
    assert entrar(cliente, senha=nova).status_code == 200
