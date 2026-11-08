"""Entidades do domínio. Este arquivo é o contrato entre crawler, API e banco."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, HttpUrl


class Plataforma(StrEnum):
    GOOGLE_SITES = "google_sites"
    WORDPRESS = "wordpress"
    GENERICO = "generico"


class TipoDocumento(StrEnum):
    """Tipo do documento curricular coletado. Marília, por exemplo, só publica matriz e ementa."""

    PPC = "ppc"
    MATRIZ = "matriz"
    EMENTARIO = "ementario"


class OrigemVersao(StrEnum):
    CRAWLER = "crawler"
    UPLOAD = "upload"  # upload manual pela API (ex.: PPCs do Drive de Pompeia)


class StatusColeta(StrEnum):
    NOVO_PPC = "novo_ppc"
    SEM_MUDANCA = "sem_mudanca"
    SEM_PPC = "sem_ppc"
    ERRO_HTTP = "erro_http"
    ERRO_DRIVE = "erro_drive"
    NAO_PDF = "nao_pdf"


class CursoSeed(BaseModel):
    """Curso cadastrado no seed, com a página onde a unidade publica seus documentos."""

    slug: str
    nome: str
    url: HttpUrl


class Unidade(BaseModel):
    slug: str
    nome: str
    cidade: str
    site_url: HttpUrl
    plataforma: Plataforma
    cursos: list[CursoSeed] = []
    ativa: bool = True


class PPCEncontrado(BaseModel):
    """Saída do crawler para cada versão nova de documento baixada (uma linha do JSONL)."""

    unidade_slug: str
    curso_slug: str
    curso_nome: str
    tipo_documento: TipoDocumento = TipoDocumento.PPC
    origem: OrigemVersao = OrigemVersao.CRAWLER
    pagina_url: HttpUrl
    arquivo_url: HttpUrl | None  # None no upload manual
    titulo_link: str
    formato: str = "pdf"
    sha256: str
    caminho_local: str
    caminho_texto: str | None = None
    tamanho_bytes: int
    paginas: int | None = None
    precisa_ocr: bool = False
    so_arquivo_mudou: bool = False  # texto igual ao da versão anterior do mesmo documento
    coletado_em: datetime


class Coleta(BaseModel):
    """Uma linha de log por curso (e por documento, quando há) em cada rodada do crawler."""

    unidade_slug: str
    curso_slug: str
    curso_nome: str
    iniciada_em: datetime
    status: StatusColeta
    detalhe: dict[str, str | int | float | bool | None] = {}


class Perfil(StrEnum):
    CONSULTA = "consulta"
    COORDENADOR = "coordenador"  # envia documentos da própria unidade
    ADMIN_POLO = "admin_polo"  # envia documentos de qualquer unidade


class Usuario(BaseModel):
    """Conta de acesso. O hash da senha não faz parte da entidade: não sai do repositório."""

    id: int
    email: str
    nome: str
    perfil: Perfil
    unidade_slug: str | None = None
    ativo: bool = True


class TipoAviso(StrEnum):
    """Problema que impede a coleta e precisa de ação humana. Aparece como aviso no front-end."""

    DRIVE_BLOQUEADO = "drive_bloqueado"  # o robots.txt do Drive proíbe o download direto


class Aviso(BaseModel):
    """Aviso aberto sobre um documento que o crawler encontrou mas não pôde baixar.

    Um aviso por (unidade, curso, arquivo_url). Some quando a unidade é coletada de novo e o
    problema não aparece mais.
    """

    tipo: TipoAviso
    unidade_slug: str
    curso_slug: str
    curso_nome: str
    tipo_documento: TipoDocumento = TipoDocumento.PPC
    pagina_url: HttpUrl
    arquivo_url: HttpUrl
    titulo_link: str = ""
    mensagem: str
    detectado_em: datetime  # primeira rodada em que apareceu
    visto_em: datetime  # última rodada em que continuava aberto
