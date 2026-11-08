from typing import Annotated

from fastapi import APIRouter, Depends, Query

from fatecorg_api.deps import SessaoDep, exigir_admin
from fatecorg_core.domain import Coleta, StatusColeta
from fatecorg_core.repositories import ColetaRepo

router = APIRouter(tags=["coletas"], dependencies=[Depends(exigir_admin)])
SlugQuery = Annotated[str | None, Query(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")]


@router.get("/coletas", responses={401: {}, 403: {}})
def listar_coletas(
    s: SessaoDep, unidade: SlugQuery = None, status: StatusColeta | None = None
) -> list[Coleta]:
    """Resultado da rodada mais recente de cada curso: o painel de saúde do crawler."""
    coletas = ColetaRepo(s).ultima_rodada_por_curso(unidade)
    return [c for c in coletas if status is None or c.status is status]
