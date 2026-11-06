"""Conexão com o banco. A URL vem de `DATABASE_URL` (no `.env`, gerado por `make env`)."""

from collections.abc import Iterator
from contextlib import contextmanager

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class BancoSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""


def criar_engine(url: str | None = None) -> Engine:
    url = url or BancoSettings().database_url
    if not url:
        raise RuntimeError("defina DATABASE_URL no .env (make env)")
    return create_engine(url, pool_pre_ping=True)


@contextmanager
def sessao(engine: Engine) -> Iterator[Session]:
    """Uma transação: commit no fim, rollback se der erro."""
    with sessionmaker(engine, expire_on_commit=False).begin() as s:
        yield s
