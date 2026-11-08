"""Exporta o contrato da API para o front-end: uv run python scripts/exportar-openapi.py

O Angular gera os tipos a partir de apps/web/openapi.json (npm run api:tipos). O CI confere que
os dois arquivos estão em dia com o código da API.
"""

import json
import sys
from pathlib import Path

from fatecorg_api.config import ApiSettings
from fatecorg_api.main import create_app

DESTINO = Path(__file__).resolve().parents[1] / "apps" / "web" / "openapi.json"

# Sem .env: o contrato não depende de configuração local nem de segredos
settings = ApiSettings(_env_file=None, docs=True)  # type: ignore[call-arg]
contrato = create_app(settings=settings).openapi()
texto = json.dumps(contrato, ensure_ascii=False, indent=2) + "\n"

if "--conferir" in sys.argv:
    if not DESTINO.exists() or DESTINO.read_text(encoding="utf-8") != texto:
        sys.exit(f"{DESTINO.name} desatualizado: rode uv run python scripts/exportar-openapi.py")
    print(f"{DESTINO.name} em dia")
else:
    DESTINO.write_text(texto, encoding="utf-8")
    print(f"Contrato gravado em {DESTINO}")
