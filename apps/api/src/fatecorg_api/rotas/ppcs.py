import hashlib
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Query, Response, UploadFile, status

from fatecorg_api.deps import SessaoDep, SettingsDep, StorageDep, UsuarioQueEnviaDep
from fatecorg_api.schemas import BlocoDiff, Comparacao, Sha256, Slug, TrechoDiff, Versao
from fatecorg_core.arquivos import (
    TIPOS_MIME,
    chave_arquivo,
    chave_texto,
    detectar_formato,
    extrair_texto,
)
from fatecorg_core.comparacao import Comparacao as ComparacaoTextos
from fatecorg_core.comparacao import comparar
from fatecorg_core.domain import OrigemVersao, Perfil, PPCEncontrado, TipoDocumento
from fatecorg_core.repositories import AvisoRepo, CatalogoRepo, VersaoRepo

router = APIRouter(prefix="/ppcs", tags=["ppcs"])
SLUG = r"^[a-z0-9][a-z0-9-]{0,99}$"
SlugQuery = Annotated[str | None, Query(pattern=SLUG)]
BLOCO = 1024 * 1024
MAX_PALAVRAS_COMPARACAO = 60_000  # o maior texto real tem 20 mil; acima disso, recusa (CPU)
Sha256Query = Annotated[str, Query(pattern=r"^[0-9a-f]{64}$")]


def _versao_ou_404(s: SessaoDep, unidade: str, curso: str, sha256: str) -> PPCEncontrado:
    ppc = VersaoRepo(s).buscar(unidade, curso, sha256)
    if ppc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "versão não encontrada")
    return ppc


def _ler_storage(storage: StorageDep, chave: str) -> bytes:
    if not storage.existe(chave):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "arquivo não encontrado no storage")
    return storage.ler(chave)


@router.get("")
def listar_versoes(
    s: SessaoDep,
    unidade: SlugQuery = None,
    curso: SlugQuery = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 50,
    deslocamento: Annotated[int, Query(ge=0, le=100_000)] = 0,
) -> list[Versao]:
    """Versões de documentos, da mais recente para a mais antiga."""
    versoes = VersaoRepo(s).listar(unidade, curso, limite=limite, deslocamento=deslocamento)
    return [Versao.de(p) for p in versoes]


@lru_cache(maxsize=32)
def _comparar_em_cache(antes: str, depois: str) -> ComparacaoTextos:
    """O texto de uma versão nunca muda (identidade por SHA): o resultado pode ficar em cache."""
    return comparar(antes, depois)


def _texto_da_versao(storage: StorageDep, ppc: PPCEncontrado) -> str:
    if not ppc.caminho_texto:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"a versão {ppc.sha256[:12]} não tem texto extraído ({ppc.formato}); "
            "só PDFs com texto podem ser comparados",
        )
    return _ler_storage(storage, ppc.caminho_texto).decode("utf-8", errors="replace")


# Declarada antes de /{sha256}: senão "comparar" seria lido como SHA e daria 422
@router.get("/{unidade}/{curso}/comparar")
def comparar_versoes(
    s: SessaoDep,
    storage: StorageDep,
    unidade: Slug,
    curso: Slug,
    de: Sha256Query,
    para: Sha256Query,
) -> Comparacao:
    """Compara o texto extraído de duas versões do mesmo curso, por parágrafo e por palavra."""
    antes = _versao_ou_404(s, unidade, curso, de)
    depois = _versao_ou_404(s, unidade, curso, para)
    texto_antes, texto_depois = _texto_da_versao(storage, antes), _texto_da_versao(storage, depois)
    if max(len(texto_antes.split()), len(texto_depois.split())) > MAX_PALAVRAS_COMPARACAO:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "documento grande demais para comparar"
        )
    r = _comparar_em_cache(texto_antes, texto_depois)
    return Comparacao(
        de=Versao.de(antes),
        para=Versao.de(depois),
        palavras_adicionadas=r.palavras_adicionadas,
        palavras_removidas=r.palavras_removidas,
        semelhanca=r.semelhanca,
        blocos=[
            BlocoDiff(
                tipo=b.tipo, trechos=[TrechoDiff(tipo=t.tipo, texto=t.texto) for t in b.trechos]
            )
            for b in r.blocos
        ],
    )


@router.get("/{unidade}/{curso}/{sha256}")
def detalhar_versao(s: SessaoDep, unidade: Slug, curso: Slug, sha256: Sha256) -> Versao:
    return Versao.de(_versao_ou_404(s, unidade, curso, sha256))


@router.get("/{unidade}/{curso}/{sha256}/arquivo")
def baixar_arquivo(
    s: SessaoDep, storage: StorageDep, unidade: Slug, curso: Slug, sha256: Sha256
) -> Response:
    ppc = _versao_ou_404(s, unidade, curso, sha256)
    nome = f"{curso}-{ppc.tipo_documento}-{sha256[:12]}.{ppc.formato}"
    return Response(
        _ler_storage(storage, ppc.caminho_local),
        media_type=TIPOS_MIME.get(ppc.formato, "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@router.get("/{unidade}/{curso}/{sha256}/texto")
def baixar_texto(
    s: SessaoDep, storage: StorageDep, unidade: Slug, curso: Slug, sha256: Sha256
) -> Response:
    ppc = _versao_ou_404(s, unidade, curso, sha256)
    if not ppc.caminho_texto:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "esta versão não tem texto extraído")
    return Response(
        _ler_storage(storage, ppc.caminho_texto), media_type="text/plain; charset=utf-8"
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={401: {}, 403: {}, 404: {}, 409: {}, 413: {}, 415: {}, 503: {}},
)
def enviar_versao(
    s: SessaoDep,
    storage: StorageDep,
    settings: SettingsDep,
    usuario: UsuarioQueEnviaDep,
    arquivo: UploadFile,
    unidade: Annotated[str, Form(pattern=SLUG)],
    curso: Annotated[str, Form(pattern=SLUG)],
    tipo_documento: Annotated[TipoDocumento, Form()] = TipoDocumento.PPC,
    titulo: Annotated[str, Form(max_length=200)] = "",
) -> Versao:
    """Upload manual de um documento (ex.: PPC que o crawler não pode baixar do Drive).

    Exige login como coordenador (só a própria unidade) ou admin do polo. Fecha os avisos abertos
    do curso para o mesmo tipo de documento.
    """
    if usuario.perfil is Perfil.COORDENADOR and usuario.unidade_slug != unidade:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "sua conta só envia documentos da sua unidade"
        )
    limite = settings.max_upload_mb * 1024 * 1024
    partes, lidos = [], 0
    while bloco := arquivo.file.read(BLOCO):
        lidos += len(bloco)
        if lidos > limite:
            raise HTTPException(
                status.HTTP_413_CONTENT_TOO_LARGE, f"arquivo acima de {settings.max_upload_mb} MB"
            )
        partes.append(bloco)
    conteudo = b"".join(partes)

    formato = detectar_formato(conteudo)
    if formato is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "aceitos: pdf, doc, docx, odt ou zip"
        )
    curso_db = CatalogoRepo(s).curso_existente(unidade, curso)
    if curso_db is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unidade ou curso não cadastrado")
    sha256 = hashlib.sha256(conteudo).hexdigest()
    if VersaoRepo(s).sha_conhecido(unidade, curso, sha256):
        raise HTTPException(status.HTTP_409_CONFLICT, "esta versão já está cadastrada")

    chave = chave_arquivo(unidade, curso, sha256, formato)
    storage.guardar(chave, conteudo, TIPOS_MIME[formato])
    chave_txt, paginas, precisa_ocr, texto_extraido = None, None, False, None
    if formato == "pdf":
        texto = extrair_texto(conteudo)
        texto_extraido = texto.texto
        chave_txt = chave_texto(chave)
        storage.guardar(chave_txt, texto.texto.encode("utf-8"), "text/plain; charset=utf-8")
        paginas, precisa_ocr = texto.paginas, texto.precisa_ocr

    agora = datetime.now(UTC)
    ppc = PPCEncontrado.model_validate(
        {
            "unidade_slug": unidade, "curso_slug": curso, "curso_nome": curso_db.nome,
            "tipo_documento": tipo_documento, "origem": OrigemVersao.UPLOAD,
            "pagina_url": curso_db.pagina_url or curso_db.unidade.site_url, "arquivo_url": None,
            "titulo_link": titulo or (arquivo.filename or "")[:200], "formato": formato,
            "sha256": sha256, "caminho_local": chave, "caminho_texto": chave_txt,
            "tamanho_bytes": len(conteudo), "paginas": paginas, "precisa_ocr": precisa_ocr,
            "coletado_em": agora,
        }
    )  # fmt: skip
    VersaoRepo(s).registrar(ppc, texto_extraido, enviado_por_id=usuario.id)
    AvisoRepo(s).resolver_do_curso(unidade, curso, agora, tipo_documento)
    return Versao.de(ppc)
