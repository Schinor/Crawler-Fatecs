"""Dependências das rotas: sessão do banco, storage, configuração e autenticação do upload."""

import secrets
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from fatecorg_api.config import ApiSettings
from fatecorg_core.db import sessao
from fatecorg_core.storage import Storage


def get_settings(request: Request) -> ApiSettings:
    return request.app.state.settings


def get_storage(request: Request) -> Storage:
    return request.app.state.storage


def get_sessao(request: Request) -> Iterator[Session]:
    with sessao(request.app.state.engine) as s:
        yield s


bearer = HTTPBearer(auto_error=False)


def exigir_token_upload(
    settings: Annotated[ApiSettings, Depends(get_settings)],
    credenciais: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> None:
    if not settings.token_upload:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "upload desligado neste servidor")
    enviado = credenciais.credentials if credenciais else ""
    if not secrets.compare_digest(enviado.encode(), settings.token_upload.encode()):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "token inválido", headers={"WWW-Authenticate": "Bearer"}
        )


SessaoDep = Annotated[Session, Depends(get_sessao)]
StorageDep = Annotated[Storage, Depends(get_storage)]
SettingsDep = Annotated[ApiSettings, Depends(get_settings)]
