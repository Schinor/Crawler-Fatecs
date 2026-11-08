"""Configuração da API, lida do ambiente e do .env (prefixo API_)."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

TAMANHO_MINIMO_SEGREDO = 32


class ApiSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="API_", extra="ignore")

    # Assina os tokens de acesso. Vazio = login e upload desligados.
    jwt_segredo: str = ""
    jwt_minutos: int = 15
    refresh_dias: int = 7
    # O refresh token vai em cookie HttpOnly. Caminho = como o NAVEGADOR enxerga a rota, com /api
    cookie_seguro: bool = True
    cookie_caminho: str = "/api/auth"
    max_upload_mb: int = 50
    # Origens do front-end (separadas por vírgula). O Angular de desenvolvimento roda na 4200.
    cors_origens: str = "http://localhost:4200"
    # /docs e /openapi.json. Em produção, desligue (API_DOCS=false) ou proteja no proxy.
    docs: bool = True

    @field_validator("jwt_segredo")
    @classmethod
    def segredo_forte(cls, valor: str) -> str:
        if valor and len(valor) < TAMANHO_MINIMO_SEGREDO:
            raise ValueError(f"API_JWT_SEGREDO precisa de {TAMANHO_MINIMO_SEGREDO}+ caracteres")
        return valor

    @property
    def lista_cors(self) -> list[str]:
        return [o.strip() for o in self.cors_origens.split(",") if o.strip()]
