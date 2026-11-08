"""Formato das respostas. Não expõe as chaves internas do storage: o front usa os links."""

from datetime import datetime
from typing import Annotated

from fastapi import Path
from pydantic import BaseModel

from fatecorg_core.domain import OrigemVersao, PPCEncontrado, TipoDocumento

Slug = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")]
Sha256 = Annotated[str, Path(pattern=r"^[0-9a-f]{64}$")]


class Links(BaseModel):
    arquivo: str
    texto: str | None


class Versao(BaseModel):
    unidade: str
    curso: str
    curso_nome: str
    tipo_documento: TipoDocumento
    origem: OrigemVersao
    formato: str
    sha256: str
    tamanho_bytes: int
    paginas: int | None
    precisa_ocr: bool
    titulo: str
    pagina_url: str
    arquivo_url: str | None
    coletado_em: datetime
    links: Links

    @classmethod
    def de(cls, p: PPCEncontrado) -> "Versao":
        base = f"/ppcs/{p.unidade_slug}/{p.curso_slug}/{p.sha256}"
        texto = f"{base}/texto" if p.caminho_texto else None
        return cls(
            unidade=p.unidade_slug, curso=p.curso_slug, curso_nome=p.curso_nome,
            tipo_documento=p.tipo_documento, origem=p.origem, formato=p.formato,
            sha256=p.sha256, tamanho_bytes=p.tamanho_bytes, paginas=p.paginas,
            precisa_ocr=p.precisa_ocr, titulo=p.titulo_link, pagina_url=str(p.pagina_url),
            arquivo_url=str(p.arquivo_url) if p.arquivo_url else None,
            coletado_em=p.coletado_em,
            links=Links(arquivo=f"{base}/arquivo", texto=texto),
        )  # fmt: skip
