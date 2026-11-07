"""Configuração da API, lida do ambiente e do .env (prefixo API_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="API_", extra="ignore")

    # Token do upload manual (Authorization: Bearer <token>). Vazio = upload desligado.
    token_upload: str = ""
    max_upload_mb: int = 50
    # Origens do front-end (separadas por vírgula). O Angular de desenvolvimento roda na 4200.
    cors_origens: str = "http://localhost:4200"
    # /docs e /openapi.json. Em produção, desligue (API_DOCS=false) ou proteja no proxy.
    docs: bool = True

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origens.split(",") if o.strip()]
