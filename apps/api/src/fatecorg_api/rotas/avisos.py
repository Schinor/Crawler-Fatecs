from typing import Annotated

from fastapi import APIRouter, Query

from fatecorg_api.deps import SessaoDep
from fatecorg_core.domain import Aviso
from fatecorg_core.repositories import AvisoRepo

router = APIRouter(tags=["avisos"])
SlugQuery = Annotated[str | None, Query(pattern=r"^[a-z0-9][a-z0-9-]{0,99}$")]


@router.get("/avisos")
def listar_avisos(s: SessaoDep, unidade: SlugQuery = None, curso: SlugQuery = None) -> list[Aviso]:
    """Avisos abertos para o banner do front-end (ex.: PPC no Drive bloqueado pelo robots.txt)."""
    return AvisoRepo(s).abertos(unidade, curso)
