"""API do FatecOrg. Desenvolvimento: `uv run uvicorn fatecorg_api.main:app --reload`."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import Engine

from fatecorg_api.config import ApiSettings
from fatecorg_api.rotas import avisos, catalogo, ppcs
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

    app = FastAPI(title="FatecOrg API", version="0.2.0", lifespan=lifespan)
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
    return app


app = create_app()
