"""Onde ficam os arquivos dos documentos. Fase 2: Garage (S3); testes e Fase 1: pasta local.

As chaves são as mesmas nos dois: `ppcs/<unidade>/<curso>/<sha256>.<formato>`.
"""

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from pydantic_settings import BaseSettings, SettingsConfigDict

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client


class Storage(Protocol):
    def guardar(self, chave: str, conteudo: bytes, content_type: str) -> None: ...
    def ler(self, chave: str) -> bytes: ...
    def existe(self, chave: str) -> bool: ...


class S3Settings(BaseSettings):
    """Variáveis `S3_*` do `.env` (geradas por `make env`)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="S3_", extra="ignore")

    endpoint: str = "http://localhost:3900"
    region: str = "garage"
    access_key: str = ""
    secret_key: str = ""
    bucket: str = "ppcs"


class S3Storage:
    """Garage ou qualquer S3 compatível. O Garage exige endereçamento por caminho."""

    def __init__(self, settings: S3Settings | None = None, *, cliente: "S3Client | None" = None):
        self.settings = settings or S3Settings()
        self.bucket = self.settings.bucket
        self.cliente: S3Client = cliente or boto3.client(
            "s3",
            endpoint_url=self.settings.endpoint,
            region_name=self.settings.region,
            aws_access_key_id=self.settings.access_key,
            aws_secret_access_key=self.settings.secret_key,
            config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
        )

    def guardar(self, chave: str, conteudo: bytes, content_type: str) -> None:
        self.cliente.put_object(
            Bucket=self.bucket, Key=chave, Body=conteudo, ContentType=content_type
        )

    def ler(self, chave: str) -> bytes:
        return self.cliente.get_object(Bucket=self.bucket, Key=chave)["Body"].read()

    def existe(self, chave: str) -> bool:
        try:
            self.cliente.head_object(Bucket=self.bucket, Key=chave)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True


class LocalStorage:
    """Pasta local (`data/`). Recusa chaves que saiam da pasta."""

    def __init__(self, raiz: Path):
        self.raiz = raiz.resolve()

    def _caminho(self, chave: str) -> Path:
        caminho = (self.raiz / chave).resolve()
        if not caminho.is_relative_to(self.raiz):
            raise ValueError(f"chave fora do storage: {chave}")
        return caminho

    def guardar(self, chave: str, conteudo: bytes, content_type: str) -> None:
        caminho = self._caminho(chave)
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_bytes(conteudo)

    def ler(self, chave: str) -> bytes:
        return self._caminho(chave).read_bytes()

    def existe(self, chave: str) -> bool:
        return self._caminho(chave).is_file()


__all__ = ["LocalStorage", "S3Settings", "S3Storage", "Storage"]
