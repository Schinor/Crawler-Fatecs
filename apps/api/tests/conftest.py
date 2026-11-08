from datetime import UTC, datetime

import pymupdf
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from fatecorg_api.auth import emitir_acesso, gerar_hash
from fatecorg_api.config import ApiSettings
from fatecorg_api.main import create_app
from fatecorg_core.db import Base, sessao
from fatecorg_core.domain import Aviso, Perfil, PPCEncontrado, TipoAviso, Unidade, Usuario
from fatecorg_core.repositories import AvisoRepo, CatalogoRepo, UsuarioRepo, VersaoRepo
from fatecorg_core.storage import LocalStorage

SEGREDO = "segredo-de-teste-" + "x" * 32
SENHA = "senha-de-teste-longa"
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


def _settings(**config) -> ApiSettings:
    base = {"jwt_segredo": SEGREDO, "cookie_seguro": False, "cookie_caminho": "/auth"}
    return ApiSettings(_env_file=None, **(base | config))  # type: ignore[call-arg]


@pytest.fixture
def fazer_cliente(engine, storage):
    def fabrica(**config) -> TestClient:
        return TestClient(create_app(engine=engine, storage=storage, settings=_settings(**config)))

    return fabrica


@pytest.fixture
def cliente(fazer_cliente) -> TestClient:
    return fazer_cliente()


@pytest.fixture
def criar_usuario(engine):
    def fabrica(
        perfil: Perfil = Perfil.ADMIN_POLO,
        email: str = "admin@teste.invalid",
        senha: str = SENHA,
        unidade: str | None = None,
    ) -> Usuario:
        with sessao(engine) as s:
            return UsuarioRepo(s).criar(email, "Pessoa", gerar_hash(senha), perfil, unidade)

    return fabrica


@pytest.fixture
def cabecalho():
    def montar(usuario: Usuario) -> dict[str, str]:
        token = emitir_acesso(_settings(), usuario, datetime.now(UTC))
        return {"Authorization": f"Bearer {token}"}

    return montar


@pytest.fixture
def sha() -> str:
    return SHA


@pytest.fixture
def auth(criar_usuario, cabecalho) -> dict[str, str]:
    return cabecalho(criar_usuario())


@pytest.fixture
def fazer_pdf():
    return pdf
