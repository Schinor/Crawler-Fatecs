from collections.abc import Callable
from pathlib import Path

import httpx
import pymupdf
import pytest

from fatecorg_crawler.config import CrawlerSettings
from fatecorg_crawler.fetch import Fetcher

FIXTURES = Path(__file__).parent / "fixtures"
Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def settings(tmp_path: Path) -> CrawlerSettings:
    return CrawlerSettings(_env_file=None, data_dir=tmp_path / "data", delay_seconds=2.0)  # type: ignore[call-arg]


class Relogio:
    """Relógio falso: dormir avança o tempo, e registramos cada espera."""

    def __init__(self) -> None:
        self.agora = 1000.0
        self.esperas: list[float] = []

    def __call__(self) -> float:
        return self.agora

    def dormir(self, segundos: float) -> None:
        self.esperas.append(segundos)
        self.agora += segundos


@pytest.fixture
def relogio() -> Relogio:
    return Relogio()


@pytest.fixture
def fazer_fetcher(settings: CrawlerSettings, relogio: Relogio) -> Callable[[Handler], Fetcher]:
    def fabrica(handler: Handler) -> Fetcher:
        return Fetcher(
            settings,
            transport=httpx.MockTransport(handler),
            dormir=relogio.dormir,
            relogio=relogio,
        )

    return fabrica


@pytest.fixture
def ler_fixture() -> Callable[[str], str]:
    return lambda nome: (FIXTURES / nome).read_text(encoding="utf-8")


def _pdf_com_texto(texto: str) -> bytes:
    doc = pymupdf.open()
    pagina = doc.new_page()
    pagina.insert_textbox(pymupdf.Rect(40, 40, 560, 800), texto, fontsize=9)  # type: ignore[attr-defined]
    dados = doc.tobytes()
    doc.close()
    return dados


@pytest.fixture
def pdf_com_texto() -> Callable[[str], bytes]:
    return _pdf_com_texto
