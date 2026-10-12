#!/usr/bin/env bash
# Cria o esqueleto do monorepo BD PPCs (Python com uv workspace + pasta do Angular).
# Uso: bash bootstrap_monorepo.sh [pasta_destino]
#   Depois: cd <pasta> && uv sync --all-packages && uv run pytest
#   O Angular é gerado à parte (ver 01_MONOREPO_E_GITHUB.md, passo 4).
set -euo pipefail

ROOT="${1:-bd-ppcs}"
if [ -e "$ROOT" ]; then
  echo "A pasta '$ROOT' já existe. Escolha outro destino." >&2
  exit 1
fi

mkdir -p "$ROOT" && cd "$ROOT"

# ---------------------------------------------------------------- pastas
mkdir -p \
  .github/workflows .github/ISSUE_TEMPLATE \
  apps/web \
  apps/api/src/bd_ppcs_api apps/api/tests \
  apps/crawler/src/bd_ppcs_crawler/sources \
  apps/crawler/seeds \
  apps/crawler/tests/fixtures \
  packages/core/src/bd_ppcs_core/domain \
  packages/core/src/bd_ppcs_core/repositories \
  packages/core/src/bd_ppcs_core/storage \
  packages/core/tests \
  infra/migrations \
  docs/adr \
  data

# ---------------------------------------------------------------- raiz
cat > .python-version <<'EOF'
3.12
EOF

cat > pyproject.toml <<'EOF'
[project]
name = "bd-ppcs"
version = "0.1.0"
description = "Coleta, versionamento e consulta dos PPCs das Fatecs do Polo Regional 08 (CPS)"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/core", "apps/crawler", "apps/api"]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6", "pyright>=1.1.380"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.ruff.lint.isort]
known-first-party = ["bd_ppcs_core", "bd_ppcs_crawler", "bd_ppcs_api"]

[tool.pytest.ini_options]
testpaths = ["packages/core/tests", "apps/crawler/tests", "apps/api/tests"]
addopts = "--import-mode=importlib"

[tool.pyright]
include = ["packages", "apps/crawler", "apps/api"]
typeCheckingMode = "basic"
EOF

cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
.ruff_cache/
*.egg-info/

# Dados coletados (nunca versionar PDFs e HTML bruto)
data/
!data/.gitkeep

# Ambiente
.env

# Node / Angular
node_modules/
apps/web/dist/
apps/web/.angular/

# IDE
.vscode/*
!.vscode/extensions.json
.idea/
EOF
touch data/.gitkeep

cat > .editorconfig <<'EOF'
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 4

[*.{ts,html,scss,json,yml,yaml,md}]
indent_size = 2
EOF

cat > .env.example <<'EOF'
# Banco
DATABASE_URL=postgresql+psycopg://bdppcs:bdppcs@localhost:5432/bdppcs

# Object storage (MinIO no dev)
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=bdppcs
S3_SECRET_KEY=bdppcs-secret
S3_BUCKET=ppcs

# Crawler
CRAWLER_USER_AGENT=BD-PPCs-Crawler/0.1 (+https://github.com/<org>/bd-ppcs; contato: <email-da-equipe>)
CRAWLER_DELAY_SECONDS=2.0
CRAWLER_DATA_DIR=./data
EOF

cat > Makefile <<'EOF'
.PHONY: setup lint test infra-up infra-down crawl

setup:      ## instala todas as dependências Python do workspace
	uv sync --all-packages

lint:       ## lint + checagem de formatação
	uv run ruff check .
	uv run ruff format --check .

test:       ## roda todos os testes Python
	uv run pytest

infra-up:   ## sobe Postgres e MinIO
	docker compose -f infra/docker-compose.yml up -d

infra-down:
	docker compose -f infra/docker-compose.yml down

crawl:      ## coleta uma unidade: make crawl U=pompeia
	uv run bd-ppcs-crawler run --unidade $(U)
EOF

cat > README.md <<'EOF'
# BD PPCs

Coleta automatizada, versionamento e consulta dos Projetos Pedagógicos de Cursos (PPCs)
das Fatecs do Polo Regional 08 do Centro Paula Souza.

Projeto Integrador de Sistemas Inteligentes III, Fatec Pompeia, 2026/2.

## Estrutura

| Pasta | Conteúdo | Responsável |
| --- | --- | --- |
| `apps/crawler` | Coleta dos sites, download e extração dos PPCs | Marcio |
| `apps/api` | API FastAPI | João |
| `apps/web` | Front-end Angular | Amabili |
| `packages/core` | Domínio compartilhado (entidades, repositórios, storage) | João + Marcio |
| `infra` | Docker Compose, migrations, nuvem | Ígor |
| `docs` | Requisitos, ADRs, contrato de dados | Leonardo |

## Primeiros passos

```bash
uv sync --all-packages     # dependências Python
make test                  # testes
make infra-up              # Postgres + MinIO (precisa de Docker)
uv run bd-ppcs-crawler --help
```
EOF

# ---------------------------------------------------------------- GitHub
cat > .github/workflows/ci.yml <<'EOF'
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v6
      - run: uv sync --all-packages
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run pytest

  web:
    runs-on: ubuntu-latest
    if: ${{ hashFiles('apps/web/package.json') != '' }}
    defaults:
      run:
        working-directory: apps/web
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - run: npm ci
      - run: npx ng build
EOF

cat > .github/CODEOWNERS <<'EOF'
# Substitua pelos usuários do GitHub de cada membro
/apps/crawler/   @usuario-marcio
/apps/api/       @usuario-joao
/apps/web/       @usuario-amabili
/packages/core/  @usuario-joao @usuario-marcio
/infra/          @usuario-igor
/docs/           @usuario-leonardo
EOF

cat > .github/pull_request_template.md <<'EOF'
## O que muda

## Issue
Closes #

## Como testar

## Checklist
- [ ] `make lint` e `make test` passam
- [ ] Atualizei o `docs/contrato-dados.md` se mudei algum campo
EOF

cat > .github/ISSUE_TEMPLATE/tarefa.md <<'EOF'
---
name: Tarefa
about: Uma tarefa do backlog
labels: ""
---

## Objetivo

## Critério de pronto
- [ ]

## Módulo
crawler / core / api / web / infra / docs
EOF

# ---------------------------------------------------------------- packages/core
cat > packages/core/pyproject.toml <<'EOF'
[project]
name = "bd-ppcs-core"
version = "0.1.0"
description = "Domínio compartilhado do BD PPCs"
requires-python = ">=3.12"
dependencies = ["pydantic>=2.7"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/bd_ppcs_core"]
EOF

cat > packages/core/src/bd_ppcs_core/__init__.py <<'EOF'
"""Domínio compartilhado do BD PPCs."""
EOF
touch packages/core/src/bd_ppcs_core/repositories/__init__.py \
      packages/core/src/bd_ppcs_core/storage/__init__.py

cat > packages/core/src/bd_ppcs_core/domain/__init__.py <<'EOF'
from bd_ppcs_core.domain.models import Plataforma, PPCEncontrado, Unidade

__all__ = ["Plataforma", "PPCEncontrado", "Unidade"]
EOF

cat > packages/core/src/bd_ppcs_core/domain/models.py <<'EOF'
"""Entidades do domínio. Este arquivo é o contrato entre crawler, API e banco."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, HttpUrl


class Plataforma(StrEnum):
    GOOGLE_SITES = "google_sites"
    WORDPRESS = "wordpress"
    GENERICO = "generico"


class Unidade(BaseModel):
    slug: str
    nome: str
    cidade: str
    site_url: HttpUrl
    plataforma: Plataforma
    paginas_cursos: list[HttpUrl] = []
    ativa: bool = True


class PPCEncontrado(BaseModel):
    """Saída do crawler para cada PPC baixado (uma linha do JSONL)."""

    unidade_slug: str
    curso_nome: str
    pagina_url: HttpUrl
    arquivo_url: HttpUrl
    titulo_link: str
    sha256: str
    caminho_local: str
    tamanho_bytes: int
    coletado_em: datetime
EOF

cat > packages/core/tests/test_models.py <<'EOF'
from datetime import UTC, datetime

from bd_ppcs_core.domain import PPCEncontrado


def test_ppc_encontrado_valida_urls():
    ppc = PPCEncontrado(
        unidade_slug="pompeia",
        curso_nome="Sistemas Inteligentes",
        pagina_url="https://www.fatecpompeia.edu.br/sistemas-inteligentes",
        arquivo_url="https://drive.google.com/uc?export=download&id=abc",
        titulo_link="PPC CST Sistemas Inteligentes",
        sha256="0" * 64,
        caminho_local="data/ppcs/pompeia/x.pdf",
        tamanho_bytes=1024,
        coletado_em=datetime.now(UTC),
    )
    assert ppc.unidade_slug == "pompeia"
EOF

# ---------------------------------------------------------------- apps/crawler
cat > apps/crawler/pyproject.toml <<'EOF'
[project]
name = "bd-ppcs-crawler"
version = "0.1.0"
description = "Crawler dos PPCs das Fatecs"
requires-python = ">=3.12"
dependencies = [
  "bd-ppcs-core",
  "httpx>=0.27",
  "beautifulsoup4>=4.12",
  "lxml>=5.2",
  "tenacity>=8.5",
  "typer>=0.12",
  "pyyaml>=6.0",
  "pymupdf>=1.24",
]

[project.scripts]
bd-ppcs-crawler = "bd_ppcs_crawler.cli:app"

[tool.uv.sources]
bd-ppcs-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/bd_ppcs_crawler"]
EOF

cat > apps/crawler/src/bd_ppcs_crawler/__init__.py <<'EOF'
"""Crawler dos PPCs das Fatecs do Polo Regional 08."""
EOF

cat > apps/crawler/src/bd_ppcs_crawler/drive.py <<'EOF'
"""Utilitários para links do Google Drive (Google Sites incorpora PPCs como arquivos do Drive)."""

import re

_PADROES_ID = (
    re.compile(r"drive\.google\.com/file/d/([\w-]{10,})"),
    re.compile(r"drive\.google\.com/(?:open|uc)\?(?:.*&)?id=([\w-]{10,})"),
    re.compile(r"docs\.google\.com/(?:document|presentation|spreadsheets)/d/([\w-]{10,})"),
)


def extrair_drive_id(url: str) -> str | None:
    """Devolve o ID do arquivo do Drive presente na URL, ou None."""
    for padrao in _PADROES_ID:
        if m := padrao.search(url):
            return m.group(1)
    return None


def url_download_direto(drive_id: str) -> str:
    return f"https://drive.google.com/uc?export=download&id={drive_id}"
EOF

cat > apps/crawler/src/bd_ppcs_crawler/discover.py <<'EOF'
"""Encontra links de PPC numa página HTML, sem seletor específico por site."""

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from bd_ppcs_crawler.drive import extrair_drive_id

PADRAO_PPC = re.compile(
    r"\bppc\b|projeto\s+pedag[oó]gico|plano\s+pedag[oó]gico|matriz\s+curricular",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LinkCandidato:
    url: str
    texto: str
    origem: str  # "a" (link) ou "iframe"
    drive_id: str | None


def _parece_documento(url: str) -> bool:
    return url.lower().split("?")[0].endswith(".pdf") or extrair_drive_id(url) is not None


def encontrar_links_ppc(html: str, base_url: str) -> list[LinkCandidato]:
    """Links e iframes cujo texto, title ou URL mencionem PPC e apontem para PDF ou Drive."""
    soup = BeautifulSoup(html, "lxml")
    vistos: set[str] = set()
    achados: list[LinkCandidato] = []

    for tag in soup.find_all(["a", "iframe"]):
        bruto = tag.get("href") if tag.name == "a" else tag.get("src")
        if not bruto:
            continue
        url = urljoin(base_url, str(bruto))
        partes = [
            tag.get_text(" ", strip=True),
            str(tag.get("title") or ""),
            str(tag.get("aria-label") or ""),
        ]
        rotulo = " ".join(p for p in partes if p)
        menciona_ppc = bool(PADRAO_PPC.search(rotulo) or PADRAO_PPC.search(url))
        if menciona_ppc and _parece_documento(url) and url not in vistos:
            vistos.add(url)
            achados.append(LinkCandidato(url, rotulo, tag.name, extrair_drive_id(url)))
    return achados
EOF

cat > apps/crawler/src/bd_ppcs_crawler/cli.py <<'EOF'
"""Linha de comando do crawler: `uv run bd-ppcs-crawler --help`."""

from pathlib import Path

import typer
import yaml

app = typer.Typer(help="Crawler dos PPCs das Fatecs do Polo Regional 08.")
SEEDS = Path(__file__).resolve().parents[2] / "seeds" / "unidades.yaml"


def _carregar_unidades() -> list[dict]:
    return yaml.safe_load(SEEDS.read_text(encoding="utf-8"))["unidades"]


@app.command()
def unidades() -> None:
    """Lista as unidades cadastradas no seed."""
    for u in _carregar_unidades():
        typer.echo(f"{u['slug']:<20} {u['plataforma']:<14} {u['site_url']}")


@app.command()
def run(unidade: str = typer.Option(..., help="slug da unidade, ex.: pompeia")) -> None:
    """Coleta uma unidade (implementação nas tarefas C3 a C6 do plano)."""
    typer.echo(f"TODO: coletar {unidade}")


if __name__ == "__main__":
    app()
EOF

for f in config fetch download extract sink; do
  cat > "apps/crawler/src/bd_ppcs_crawler/$f.py" <<EOF
"""$f: ver 02_CRAWLER.md para o que este módulo deve fazer."""
EOF
done

cat > apps/crawler/src/bd_ppcs_crawler/sources/__init__.py <<'EOF'
"""Adaptadores por plataforma (Google Sites, WordPress, genérico)."""
EOF
for f in base google_sites generico; do
  cat > "apps/crawler/src/bd_ppcs_crawler/sources/$f.py" <<EOF
"""Adaptador $f: ver 02_CRAWLER.md, tarefa C4."""
EOF
done

cat > apps/crawler/seeds/unidades.yaml <<'EOF'
# Unidades do Polo Regional 08. Confirmar a lista com a parceira (tarefa C1).
unidades:
  - slug: pompeia
    nome: Fatec Shunji Nishimura
    cidade: Pompeia
    site_url: https://www.fatecpompeia.edu.br
    plataforma: google_sites
    paginas_cursos:
      - https://www.fatecpompeia.edu.br/sistemas-inteligentes
      - https://www.fatecpompeia.edu.br/bigdata
      - https://www.fatecpompeia.edu.br/map
  # - slug: ...
EOF

cat > apps/crawler/tests/fixtures/README.md <<'EOF'
HTML salvo de cada unidade (`<slug>_<curso>.html`). Usado nos testes de snapshot do parser.
EOF

cat > apps/crawler/tests/test_discover.py <<'EOF'
from bd_ppcs_crawler.discover import encontrar_links_ppc
from bd_ppcs_crawler.drive import extrair_drive_id, url_download_direto

HTML_GOOGLE_SITES = """
<html><body>
  <a href="/secretaria/ementa">Ementa</a>
  <a href="https://drive.google.com/file/d/1XyZ0123456789ab/view">Deliberação 106</a>
  <iframe title="PPC CST Sistemas Inteligentes - Fatec Pompeia.pdf"
          src="https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/preview"></iframe>
  <a href="/docs/Projeto_Pedagogico_BigData.pdf">Projeto Pedagógico do Curso</a>
</body></html>
"""


def test_extrai_id_do_drive():
    assert extrair_drive_id("https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/preview") == (
        "1AbCdEfGhIjKlMnOpQrStUv"
    )
    assert extrair_drive_id("https://drive.google.com/open?id=1AbCdEfGhIjKlMnOpQrStUv") == (
        "1AbCdEfGhIjKlMnOpQrStUv"
    )
    assert extrair_drive_id("https://www.fatecpompeia.edu.br/map") is None


def test_url_download_direto():
    assert url_download_direto("abc123def456").endswith("id=abc123def456")


def test_encontra_iframe_do_drive_e_pdf_ignorando_outros_documentos():
    links = encontrar_links_ppc(HTML_GOOGLE_SITES, "https://www.fatecpompeia.edu.br/x")
    urls = {link.url for link in links}
    assert "https://drive.google.com/file/d/1AbCdEfGhIjKlMnOpQrStUv/preview" in urls
    assert "https://www.fatecpompeia.edu.br/docs/Projeto_Pedagogico_BigData.pdf" in urls
    assert len(links) == 2  # a Deliberação 106 fica de fora
EOF

# ---------------------------------------------------------------- apps/api
cat > apps/api/pyproject.toml <<'EOF'
[project]
name = "bd-ppcs-api"
version = "0.1.0"
description = "API do BD PPCs"
requires-python = ">=3.12"
dependencies = ["bd-ppcs-core", "fastapi>=0.115", "uvicorn[standard]>=0.30"]

[tool.uv.sources]
bd-ppcs-core = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/bd_ppcs_api"]
EOF

cat > apps/api/src/bd_ppcs_api/__init__.py <<'EOF'
EOF

cat > apps/api/src/bd_ppcs_api/main.py <<'EOF'
from fastapi import FastAPI

app = FastAPI(title="BD PPCs API", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
EOF

cat > apps/api/tests/test_health.py <<'EOF'
from fastapi.testclient import TestClient

from bd_ppcs_api.main import app


def test_health():
    assert TestClient(app).get("/health").json() == {"status": "ok"}
EOF

# ---------------------------------------------------------------- apps/web
cat > apps/web/README.md <<'EOF'
Front-end Angular. Gerar a partir da raiz do repositório (passo 4 de 01_MONOREPO_E_GITHUB.md).
Requer Node 24 LTS (o Angular CLI atual exige Node >= 22.22.3 ou >= 24.15).

    rm apps/web/README.md
    npx @angular/cli@latest new web --directory apps/web --routing --style=scss --ssr=false --skip-git
    cd apps/web && npm install   # gera o package-lock.json que o CI usa
EOF

# ---------------------------------------------------------------- infra
cat > infra/docker-compose.yml <<'EOF'
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: bdppcs
      POSTGRES_PASSWORD: bdppcs
      POSTGRES_DB: bdppcs
    ports: ["5432:5432"]
    volumes: [pgdata:/var/lib/postgresql/data]

  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: bdppcs
      MINIO_ROOT_PASSWORD: bdppcs-secret
    ports: ["9000:9000", "9001:9001"]
    volumes: [miniodata:/data]

volumes:
  pgdata:
  miniodata:
EOF
touch infra/migrations/.gitkeep

# ---------------------------------------------------------------- docs
cat > docs/adr/0001-monorepo-uv-workspace.md <<'EOF'
# ADR 0001: Monorepo com uv workspace

Status: aceito

## Contexto
Crawler e API gravam as mesmas entidades (Unidade, Curso, VersãoPPC). Em repositórios
separados o contrato de dados viraria um acordo verbal.

## Decisão
Um repositório. Python em uv workspace (`packages/core`, `apps/crawler`, `apps/api`);
Angular em `apps/web` com npm próprio.

## Consequências
Um único `uv.lock`; mudança no domínio quebra o CI de quem depende dele no mesmo PR.
EOF

cat > docs/contrato-dados.md <<'EOF'
# Contrato de dados

Fonte da verdade: `packages/core/src/bd_ppcs_core/domain/models.py`.

## Saída do crawler (MVP, antes do banco): `data/ppcs/ppcs.jsonl`
Uma linha por PPC baixado, no formato `PPCEncontrado`.
EOF

echo "Monorepo criado em $(pwd)"
echo "Próximo passo: cd $ROOT && uv sync --all-packages && uv run pytest"
