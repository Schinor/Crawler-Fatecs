"""Login. O token de acesso volta no corpo; o refresh, em cookie HttpOnly (fora do alcance do JS).

Cada rota abre a própria transação: o contador de falhas e o encerramento de sessões precisam ser
gravados mesmo quando a resposta é 401.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fatecorg_api.auth import (
    emitir_acesso,
    gastar_tempo_de_verificacao,
    gerar_hash,
    novo_refresh,
    precisa_novo_hash,
    senha_confere,
    sha256_do_refresh,
)
from fatecorg_api.config import ApiSettings
from fatecorg_api.deps import EngineDep, SettingsDep, exigir_login_ligado
from fatecorg_core.db import sessao
from fatecorg_core.domain import Usuario
from fatecorg_core.repositories import SessaoLoginRepo, UsuarioRepo

router = APIRouter(prefix="/auth", tags=["login"], dependencies=[Depends(exigir_login_ligado)])
COOKIE = "fatecorg_refresh"
CookieRefresh = Annotated[str | None, Cookie(alias=COOKIE, max_length=128)]
LOGIN_RECUSADO = "e-mail ou senha incorretos, ou conta bloqueada por tentativas demais"
REFRESH_RECUSADO = "sessão expirada ou inválida; entre novamente"


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    # Limite do lado do servidor: senha enorme é custo de CPU no Argon2
    senha: str = Field(min_length=1, max_length=128)


class SessaoAberta(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expira_em_segundos: int
    usuario: Usuario


def _gravar_cookie(resposta: Response, settings: ApiSettings, token: str) -> None:
    resposta.set_cookie(
        COOKIE,
        token,
        max_age=settings.refresh_dias * 86_400,
        path=settings.cookie_caminho,
        httponly=True,
        secure=settings.cookie_seguro,
        samesite="strict",
    )


def _apagar_cookie(resposta: Response, settings: ApiSettings) -> None:
    resposta.delete_cookie(
        COOKIE,
        path=settings.cookie_caminho,
        httponly=True,
        secure=settings.cookie_seguro,
        samesite="strict",
    )


def _sessao_aberta(settings: ApiSettings, usuario: Usuario, agora: datetime) -> SessaoAberta:
    return SessaoAberta(
        access_token=emitir_acesso(settings, usuario, agora),
        expira_em_segundos=settings.jwt_minutos * 60,
        usuario=usuario,
    )


def _autenticar(s: Session, dados: Login, agora: datetime) -> Usuario | None:
    usuarios = UsuarioRepo(s)
    credenciais = usuarios.credenciais(dados.email, agora)
    if credenciais is None or credenciais.bloqueado or not credenciais.usuario.ativo:
        gastar_tempo_de_verificacao(dados.senha)
        return None
    usuario = credenciais.usuario
    if not senha_confere(credenciais.senha_hash, dados.senha):
        usuarios.registrar_falha(usuario.id, agora)
        return None
    novo = gerar_hash(dados.senha) if precisa_novo_hash(credenciais.senha_hash) else None
    usuarios.registrar_sucesso(usuario.id, novo)
    return usuario


@router.post("/login", responses={401: {}, 503: {}})
def entrar(
    dados: Login, response: Response, engine: EngineDep, settings: SettingsDep
) -> SessaoAberta:
    """Abre uma sessão. A mesma resposta para e-mail inexistente, senha errada e conta bloqueada."""
    agora = datetime.now(UTC)
    refresh = novo_refresh()
    with sessao(engine) as s:
        usuario = _autenticar(s, dados, agora)
        if usuario is not None:
            SessaoLoginRepo(s).abrir(
                usuario.id,
                sha256_do_refresh(refresh),
                agora,
                agora + timedelta(days=settings.refresh_dias),
            )
    if usuario is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, LOGIN_RECUSADO)
    _gravar_cookie(response, settings, refresh)
    response.headers["Cache-Control"] = "no-store"
    return _sessao_aberta(settings, usuario, agora)


@router.post("/refresh", responses={204: {}, 401: {}, 503: {}})
def renovar(
    response: Response,
    engine: EngineDep,
    settings: SettingsDep,
    cookie: CookieRefresh = None,
) -> SessaoAberta:
    """Troca o refresh por outro e devolve um token de acesso. Sem cookie, 204: visitante."""
    if not cookie:
        return Response(status_code=status.HTTP_204_NO_CONTENT)  # type: ignore[return-value]
    agora = datetime.now(UTC)
    novo = novo_refresh()
    with sessao(engine) as s:
        sessoes = SessaoLoginRepo(s)
        giro = sessoes.girar(
            sha256_do_refresh(cookie),
            sha256_do_refresh(novo),
            agora,
            agora + timedelta(days=settings.refresh_dias),
        )
        usuario = UsuarioRepo(s).por_id(giro.usuario_id) if giro else None
        if giro and (usuario is None or not usuario.ativo):
            sessoes.encerrar_todas(giro.usuario_id)
            usuario = None
    if giro is None or usuario is None:
        recusa = JSONResponse({"detail": REFRESH_RECUSADO}, status.HTTP_401_UNAUTHORIZED)
        _apagar_cookie(recusa, settings)
        return recusa  # type: ignore[return-value]
    if giro.girou:
        _gravar_cookie(response, settings, novo)
    response.headers["Cache-Control"] = "no-store"
    return _sessao_aberta(settings, usuario, agora)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, responses={503: {}})
def sair(
    response: Response,
    engine: EngineDep,
    settings: SettingsDep,
    cookie: CookieRefresh = None,
) -> None:
    if cookie:
        with sessao(engine) as s:
            SessaoLoginRepo(s).encerrar(sha256_do_refresh(cookie))
    _apagar_cookie(response, settings)
