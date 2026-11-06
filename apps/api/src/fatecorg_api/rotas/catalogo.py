from fastapi import APIRouter

from fatecorg_api.deps import SessaoDep
from fatecorg_core.domain import Unidade
from fatecorg_core.repositories import CatalogoRepo

router = APIRouter(tags=["catálogo"])


@router.get("/unidades")
def listar_unidades(s: SessaoDep) -> list[Unidade]:
    """Unidades e cursos cadastrados (espelho do seed do crawler)."""
    return CatalogoRepo(s).listar()
