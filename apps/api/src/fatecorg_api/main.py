"""API do FatecOrg. Desenvolvimento: `uv run uvicorn fatecorg_api.main:app --reload`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy import Engine

from fatecorg_api.config import ApiSettings
from fatecorg_api.deps import token_valido
from fatecorg_api.rotas import avisos, busca, catalogo, ppcs
from fatecorg_core.storage import Storage


def create_app(
    *,
    engine: Engine | None = None,
    storage: Storage | None = None,
    settings: ApiSettings | None = None,
) -> FastAPI:
    """Fábrica da API. Os testes injetam SQLite e storage local; em produção vêm do .env."""
    settings = settings or ApiSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if engine is None:
            from fatecorg_core.db import criar_engine

            app.state.engine = criar_engine()
        if storage is None:
            from fatecorg_core.storage import S3Storage

            app.state.storage = S3Storage()
        yield
        if engine is None:
            app.state.engine.dispose()

    app = FastAPI(
        title="FatecOrg API",
        version="0.2.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.docs else None,
        redoc_url="/redoc" if settings.docs else None,
        openapi_url="/openapi.json" if settings.docs else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.storage = storage
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.lista_cors,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def barrar_upload_antes_do_corpo(request: Request, call_next) -> Response:
        """O FastAPI lê o corpo inteiro antes das dependências. Sem esta checagem, qualquer um
        mandaria centenas de MB antes de levar o 401 (achado A-1 do pentest)."""
        if request.method == "POST" and request.url.path.rstrip("/") == "/ppcs":
            if not settings.token_upload:
                return JSONResponse({"detail": "upload desligado neste servidor"}, 503)
            esquema, token = get_authorization_scheme_param(request.headers.get("authorization"))
            if esquema.lower() != "bearer" or not token_valido(settings, token):
                return JSONResponse(
                    {"detail": "token inválido"}, 401, headers={"WWW-Authenticate": "Bearer"}
                )
            tamanho = request.headers.get("content-length", "")
            limite = (settings.max_upload_mb + 1) * 1024 * 1024  # folga para o multipart
            if tamanho.isdigit() and int(tamanho) > limite:
                return JSONResponse(
                    {"detail": f"arquivo acima de {settings.max_upload_mb} MB"}, 413
                )
        return await call_next(request)

    @app.exception_handler(BotoCoreError)
    @app.exception_handler(ClientError)
    async def storage_indisponivel(request: Request, erro: Exception) -> JSONResponse:
        """Falha no Garage vira 503 sem detalhes internos (achado A-3)."""
        return JSONResponse({"detail": "storage indisponível, tente mais tarde"}, 503)

    @app.middleware("http")
    async def cabecalhos_de_seguranca(request: Request, call_next) -> Response:
        resposta = await call_next(request)
        resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
        resposta.headers.setdefault("Referrer-Policy", "no-referrer")
        return resposta

    @app.get("/health", tags=["infra"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(catalogo.router)
    app.include_router(ppcs.router)
    app.include_router(avisos.router)
    app.include_router(busca.router)
    return app


app = create_app()
