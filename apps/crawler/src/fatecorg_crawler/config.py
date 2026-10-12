"""Configuração do crawler, lida do ambiente e do .env (prefixo CRAWLER_)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class CrawlerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="CRAWLER_", extra="ignore")

    user_agent: str = "FatecOrg-Crawler/0.1 (+https://github.com/Schinor/Crawler-Fatecs)"
    delay_seconds: float = 2.0
    timeout_seconds: float = 30.0
    max_depth: int = 2
    data_dir: Path = Path("data")
    min_chars_texto: int = 500  # abaixo disso, o PDF provavelmente é escaneado
    # Domínios fora do site da unidade de onde aceitamos baixar documentos
    dominios_arquivos: list[str] = [
        "drive.google.com",
        "docs.google.com",
        "drive.usercontent.google.com",
        "bkpsitecpsnew.blob.core.windows.net",  # uploads dos sites WordPress do CPS
    ]
