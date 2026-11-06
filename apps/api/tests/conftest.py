from datetime import UTC, datetime

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from fatecorg_api.config import ApiSettings
from fatecorg_api.main import create_app
from fatecorg_core.db import Base, sessao
from fatecorg_core.domain import Aviso, PPCEncontrado, TipoAviso, Unidade
from fatecorg_core.repositories import AvisoRepo, CatalogoRepo, VersaoRepo
from fatecorg_core.storage import LocalStorage

TOKEN = "token-de-teste-" + "x" * 32
SHA = "a" * 64
AGORA = datetime(2026, 11, 6, 3, tzinfo=UTC)
POMPEIA = Unidade.model_validate(
    {
        "slug": "pompeia", "nome": "Fatec Pompeia", "cidade": "Pompeia",
        "site_url": "https://fatecpompeia.edu.br", "plataforma": "google_sites",
        "cursos": [
            {"slug": "ads", "nome": "ADS", "url": "https://fatecpompeia.edu.br/ads"},
            {"slug": "big-data", "nome": "Big Data", "url": "https://fatecpompeia.edu.br/bd"},
        ],
    }
)  # fmt: skip


def pdf(texto: str = "Projeto Pedagógico do Curso. " * 40) -> bytes:
    doc = pymupdf.open()
    doc.new_page().insert_text((72, 72), texto)  # type: ignore[attr-defined]
    return doc.tobytes()


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(tmp_path / "garage")


@pytest.fixture
def engine(storage):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    chave = f"ppcs/pompeia/ads/{SHA}.pdf"
    storage.guardar(chave, b"%PDF-1.7 teste", "application/pdf")
    storage.guardar(chave.replace(".pdf", ".txt"), "texto extraído".encode(), "text/plain")
    with sessao(engine) as s:
        CatalogoRepo(s).sincronizar([POMPEIA])
        VersaoRepo(s).registrar(
            PPCEncontrado.model_validate(
                {
                    "unidade_slug": "pompeia",
                    "curso_slug": "ads",
                    "curso_nome": "ADS",
                    "pagina_url": "https://fatecpompeia.edu.br/ads",
                    "arquivo_url": "https://fatecpompeia.edu.br/ppc.pdf",
                    "titulo_link": "PPC",
                    "sha256": SHA,
                    "caminho_local": chave,
                    "caminho_texto": chave.replace(".pdf", ".txt"),
                    "tamanho_bytes": 14,
                    "coletado_em": AGORA,
                }
            )  # fmt: skip
        )
        AvisoRepo(s).atualizar(
            [
                Aviso.model_validate(
                    {
                        "tipo": TipoAviso.DRIVE_BLOQUEADO,
                        "unidade_slug": "pompeia",
                        "curso_slug": "big-data",
                        "curso_nome": "Big Data",
                        "pagina_url": "https://fatecpompeia.edu.br/bd",
                        "arquivo_url": "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv",
                        "mensagem": "bloqueado",
                        "detectado_em": AGORA,
                        "visto_em": AGORA,
                    }
                )  # fmt: skip
            ],
            set(),
            AGORA,
        )
    return engine


@pytest.fixture
def fazer_cliente(engine, storage):
    def fabrica(**config) -> TestClient:
        settings = ApiSettings(_env_file=None, **config)  # type: ignore[call-arg]
        return TestClient(create_app(engine=engine, storage=storage, settings=settings))

    return fabrica


@pytest.fixture
def cliente(fazer_cliente) -> TestClient:
    return fazer_cliente(token_upload=TOKEN)


@pytest.fixture
def sha() -> str:
    return SHA


@pytest.fixture
def auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def fazer_pdf():
    return pdf
