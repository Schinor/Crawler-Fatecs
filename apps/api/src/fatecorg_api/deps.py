"""Dependências das rotas: sessão do banco, storage, configuração e usuário autenticado."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from fatecorg_api.auth import PERFIS_DE_ENVIO, ler_acesso
from fatecorg_api.config import ApiSettings
from fatecorg_core.db import sessao
from fatecorg_core.domain import Usuario
from fatecorg_core.notificacoes import NotificacaoSettings
from fatecorg_core.repositories import UsuarioRepo
from fatecorg_core.storage import Storage


def get_settings(request: Request) -> ApiSettings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_notificacao(request: Request) -> NotificacaoSettings:
    return request.app.state.notificacao


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_sessao(request: Request) -> Iterator[Session]:
    with sessao(request.app.state.engine) as s:
        yield s


SessaoDep = Annotated[Session, Depends(get_sessao)]
StorageDep = Annotated[Storage, Depends(get_storage)]
SettingsDep = Annotated[ApiSettings, Depends(get_settings)]
EngineDep = Annotated[Engine, Depends(get_engine)]
NotificacaoDep = Annotated[NotificacaoSettings, Depends(get_notificacao)]

bearer = HTTPBearer(auto_error=False)
SEM_SESSAO = "sessão expirada ou inválida; entre novamente"


def exigir_login_ligado(settings: SettingsDep) -> None:
    if not settings.jwt_segredo:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "login desligado neste servidor")


def usuario_atual(
    s: SessaoDep,
    settings: SettingsDep,
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Usuario:
    """Vai ao banco: uma conta desativada perde o acesso na hora, sem esperar o token vencer."""
    acesso = ler_acesso(settings, credenciais.credentials) if credenciais else None
    usuario = UsuarioRepo(s).por_id(acesso.usuario_id) if acesso else None
    if usuario is None or not usuario.ativo:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, SEM_SESSAO, headers={"WWW-Authenticate": "Bearer"}
        )
    return usuario


def usuario_que_envia(usuario: Annotated[Usuario, Depends(usuario_atual)]) -> Usuario:
    if usuario.perfil not in PERFIS_DE_ENVIO:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "sua conta não pode enviar documentos")
    return usuario


UsuarioQueEnviaDep = Annotated[Usuario, Depends(usuario_que_envia)]
