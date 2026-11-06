"""Persistência (Fase 2): tabelas SQLAlchemy e conexão com o Postgres."""

from fatecorg_core.db.sessao import BancoSettings, criar_engine, sessao
from fatecorg_core.db.tabelas import (
    AvisoDB,
    Base,
    ColetaDB,
    CursoDB,
    OrigemVersao,
    PPCVersaoDB,
    UnidadeDB,
)

__all__ = [
    "AvisoDB",
    "BancoSettings",
    "Base",
    "ColetaDB",
    "CursoDB",
    "OrigemVersao",
    "PPCVersaoDB",
    "UnidadeDB",
    "criar_engine",
    "sessao",
]
