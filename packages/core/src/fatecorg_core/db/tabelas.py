"""Tabelas do banco (SQLAlchemy). Espelham as entidades de `domain/models.py`.

Mudou uma tabela? Gere a migration: `make migration M="descrição"` e revise o arquivo gerado.
Os testes rodam em SQLite; por isso o JSONB e os índices parciais têm variante genérica.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    MetaData,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from fatecorg_core.domain import Plataforma, StatusColeta, TipoAviso, TipoDocumento

# Nomes previsíveis para constraints: o Alembic consegue renomear e remover sem adivinhar
NOMES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Json = JSON().with_variant(JSONB(), "postgresql")
Momento = DateTime(timezone=True)


def _enum[E: StrEnum](tipo: type[E], nome: str) -> Enum:
    """Enum guardado como texto com CHECK (não cria tipo nativo no Postgres)."""
    return Enum(
        tipo,
        name=nome,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NOMES)


class OrigemVersao(StrEnum):
    CRAWLER = "crawler"
    UPLOAD = "upload"  # upload manual pela API (ex.: PPCs do Drive de Pompeia)


class UnidadeDB(Base):
    __tablename__ = "unidade"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    nome: Mapped[str] = mapped_column(String(200))
    cidade: Mapped[str] = mapped_column(String(100))
    site_url: Mapped[str] = mapped_column(String(500))
    plataforma: Mapped[Plataforma] = mapped_column(_enum(Plataforma, "plataforma"))
    ativa: Mapped[bool] = mapped_column(default=True)
    criada_em: Mapped[datetime] = mapped_column(Momento, server_default=func.now())

    cursos: Mapped[list["CursoDB"]] = relationship(back_populates="unidade")


class CursoDB(Base):
    __tablename__ = "curso"
    __table_args__ = (UniqueConstraint("unidade_id", "slug"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id", ondelete="CASCADE"))
    slug: Mapped[str] = mapped_column(String(100))
    nome: Mapped[str] = mapped_column(String(200))
    pagina_url: Mapped[str | None] = mapped_column(String(500))

    unidade: Mapped[UnidadeDB] = relationship(back_populates="cursos")
    versoes: Mapped[list["PPCVersaoDB"]] = relationship(back_populates="curso")


class PPCVersaoDB(Base):
    """Uma versão de documento curricular. Identidade: (curso, sha256), como no dedup da Fase 1."""

    __tablename__ = "ppc_versao"
    __table_args__ = (UniqueConstraint("curso_id", "sha256"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    curso_id: Mapped[int] = mapped_column(ForeignKey("curso.id", ondelete="CASCADE"), index=True)
    tipo_documento: Mapped[TipoDocumento] = mapped_column(_enum(TipoDocumento, "tipo_documento"))
    origem: Mapped[OrigemVersao] = mapped_column(
        _enum(OrigemVersao, "origem"), default=OrigemVersao.CRAWLER
    )
    sha256: Mapped[str] = mapped_column(String(64))
    formato: Mapped[str] = mapped_column(String(10))
    tamanho_bytes: Mapped[int]
    # Mesma chave no Garage e em data/: ppcs/<unidade>/<curso>/<sha256>.<formato>
    chave_arquivo: Mapped[str] = mapped_column(String(300))
    chave_texto: Mapped[str | None] = mapped_column(String(300))
    paginas: Mapped[int | None]
    precisa_ocr: Mapped[bool] = mapped_column(default=False)
    pagina_url: Mapped[str | None] = mapped_column(String(500))
    arquivo_url: Mapped[str | None] = mapped_column(String(500))
    titulo_link: Mapped[str] = mapped_column(String(200), default="")
    # Campos específicos do PPC: vazio até o grupo e a parceira definirem (docs/decisoes.md)
    campos: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    coletado_em: Mapped[datetime] = mapped_column(Momento)

    curso: Mapped[CursoDB] = relationship(back_populates="versoes")


class ColetaDB(Base):
    """Log das rodadas. `curso_id` é nulo quando a falha foi na home da unidade."""

    __tablename__ = "coleta"

    id: Mapped[int] = mapped_column(primary_key=True)
    unidade_id: Mapped[int] = mapped_column(ForeignKey("unidade.id", ondelete="CASCADE"))
    curso_id: Mapped[int | None] = mapped_column(ForeignKey("curso.id", ondelete="CASCADE"))
    iniciada_em: Mapped[datetime] = mapped_column(Momento, index=True)
    status: Mapped[StatusColeta] = mapped_column(_enum(StatusColeta, "status_coleta"))
    detalhe: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class AvisoDB(Base):
    """Aviso para o front-end. Depois de resolvido (`resolvido_em`) fica no banco como histórico."""

    __tablename__ = "aviso"
    __table_args__ = (
        # Só um aviso aberto por documento; os resolvidos podem se repetir
        Index(
            "uq_aviso_aberto",
            "curso_id",
            "arquivo_url",
            unique=True,
            postgresql_where=text("resolvido_em IS NULL"),
            sqlite_where=text("resolvido_em IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoAviso] = mapped_column(_enum(TipoAviso, "tipo_aviso"))
    curso_id: Mapped[int] = mapped_column(ForeignKey("curso.id", ondelete="CASCADE"))
    tipo_documento: Mapped[TipoDocumento] = mapped_column(_enum(TipoDocumento, "tipo_documento"))
    pagina_url: Mapped[str] = mapped_column(String(500))
    arquivo_url: Mapped[str] = mapped_column(String(500))
    titulo_link: Mapped[str] = mapped_column(String(200), default="")
    mensagem: Mapped[str] = mapped_column(String(1000))
    detectado_em: Mapped[datetime] = mapped_column(Momento)
    visto_em: Mapped[datetime] = mapped_column(Momento)
    resolvido_em: Mapped[datetime | None] = mapped_column(Momento)

    curso: Mapped[CursoDB] = relationship()
