from typing import Annotated

from fastapi import APIRouter, Query

from fatecorg_api.deps import SessaoDep
from fatecorg_api.schemas import ResultadoBusca, TrechoBusca, Versao
from fatecorg_core.domain import TipoDocumento
from fatecorg_core.repositories import VersaoRepo

router = APIRouter(tags=["busca"])
SlugQuery = Annotated[str | None, Query(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")]


@router.get("/busca")
def buscar(
    s: SessaoDep,
    q: Annotated[str, Query(min_length=2, max_length=200)],
    unidade: SlugQuery = None,
    tipo: TipoDocumento | None = None,
    limite: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[ResultadoBusca]:
    """Busca no título e no texto extraído dos documentos, em português e sem acento.

    Aceita `"frase exata"`, `-excluir` e `termo1 or termo2`. Documentos sem texto (zip, imagem)
    só são achados pelo título.
    """
    return [
        ResultadoBusca(
            versao=Versao.de(r.ppc),
            trechos=[TrechoBusca(texto=t.texto, destaque=t.destaque) for t in r.trechos],
            relevancia=round(r.relevancia, 4),
        )
        for r in VersaoRepo(s).buscar_no_texto(q, unidade_slug=unidade, tipo=tipo, limite=limite)
    ]
