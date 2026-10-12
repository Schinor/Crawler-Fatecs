# FatecOrg

Coleta automatizada, versionamento e consulta dos Projetos Pedagógicos de Cursos (PPCs)
das Fatecs do Polo Regional 08 do Centro Paula Souza. Unidades atendidas hoje: Pompeia e Marília.

Projeto Integrador de Sistemas Inteligentes III, Fatec Pompeia, 2026/2.
Grupo Web Scraper/2: Ígor Rueda, Leonardo Oliveira, João Serrano, Amabili Flôr e Marcio Mazega.

## Como funciona

O sistema tem duas portas de entrada e uma de saída:

- **Crawler agendado** (`apps/crawler`): lê os sites das Fatecs, encontra os PPCs (PDFs ou
  arquivos do Google Drive), baixa, calcula o SHA-256 e extrai o texto;
- **Upload manual** pela API (`apps/api`, FastAPI);
- **Front-end** Angular (`apps/web`) para busca, histórico e relatórios.

Crawler e API gravam pelo mesmo domínio Python (`packages/core`), que é o contrato de dados
do projeto.

```text
Fase 1:  crawler ──► JsonlSink (data/ppcs/ppcs.jsonl)
Fase 2:  crawler ──► RepoSink  (Postgres + Garage) ◄── API ◄── Angular
```

## Estrutura

| Pasta | Conteúdo | Responsável |
| --- | --- | --- |
| `apps/crawler` | Coleta dos sites, download e extração dos PPCs | Marcio |
| `apps/api` | API FastAPI | João |
| `apps/web` | Front-end Angular | Amabili |
| `packages/core` | Domínio compartilhado (entidades, repositórios, storage) | João + Marcio |
| `infra` | Docker Compose (Postgres + Garage S3), migrations | Ígor |
| `docs` | Requisitos, ADRs, contrato de dados | Leonardo |
| `scripts` | Scripts auxiliares (ex.: `bootstrap_monorepo.sh`) | Todos |
| `data` | Saída local do crawler, **fora do Git** | — |

Os três pacotes Python formam um [uv workspace](https://docs.astral.sh/uv/concepts/projects/workspaces/):
um único `.venv` e um único `uv.lock`. Se uma entidade muda em `core`, os testes do crawler e da
API rodam no mesmo PR.

## Pré-requisitos

| Ferramenta | Versão |
| --- | --- |
| Git | recente |
| [uv](https://docs.astral.sh/uv/) | 0.5+ (instala o Python 3.12 sozinho) |
| Node.js | 24 LTS (apenas para `apps/web`) |
| Docker + Docker Compose | recente (apenas para `make infra-up`) |
| GitHub CLI (`gh`) | recente (opcional) |

No Windows, use o WSL2.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Primeiros passos

```bash
git clone git@github.com:Schinor/Crawler-Fatecs.git
cd Crawler-Fatecs
make env                         # cria o .env com segredos aleatórios
make setup                       # uv sync --all-packages
uv run pre-commit install        # hook que bloqueia segredos antes do commit
make test                        # pytest
make lint                        # ruff check + ruff format --check
uv run fatecorg-crawler --help
uv run fatecorg-crawler unidades  # lista as Fatecs do seed
```

Comandos do `Makefile`:

| Comando | O que faz |
| --- | --- |
| `make setup` | Instala todas as dependências Python do workspace |
| `make lint` | Ruff (lint + formatação) |
| `make test` | Todos os testes Python |
| `make env` | Cria o `.env` local com segredos aleatórios (rode uma vez) |
| `make infra-up` / `make infra-down` | Sobe / derruba Postgres e Garage; o `infra-up` também cria a chave e o bucket `ppcs` |
| `make crawl U=pompeia` | Coleta uma unidade |

API em modo de desenvolvimento:

```bash
uv run uvicorn fatecorg_api.main:app --reload   # http://localhost:8000/docs
```

## Fluxo de trabalho

1. Toda tarefa vira uma issue com label de módulo (`mod:crawler`, `mod:api`...) e milestone da fase.
2. Branch a partir da `main`: `feat/crawler-adaptador-google-sites`, `fix/...`, `docs/...`.
3. Commits em [Conventional Commits](https://www.conventionalcommits.org/pt-br/) com escopo:
   `feat(crawler): ...`, `fix(api): ...`, `docs: ...`, `chore(infra): ...`, `test(crawler): ...`.
4. PR com `Closes #<n>`, revisado por 1 pessoa (o `CODEOWNERS` sugere quem) e CI verde.
5. Merge com **squash**.
6. Uma tag por entrega do PI, como `v0.1.0-fase1`.

**Pronto** = PR revisado, CI verde e teste cobrindo o comportamento novo.

## Convenções

- Código e domínio em português sem acento (`unidade`, `ppc_versao`); termos técnicos
  consagrados em inglês (`fetch`, `sink`, `repository`).
- Python 3.12, Ruff (linha de 100), pytest, pyright.
- **Dados coletados nunca entram no Git**: `data/` está no `.gitignore`.
- Nunca edite o `uv.lock` à mão; em conflito, rode `uv lock` depois do rebase.

## Front-end (Angular)

Ainda não gerado. Veja `apps/web/README.md`. O job `web` do CI só roda quando existir
`apps/web/package.json`.

## Documentação

- `docs/adr/`: decisões de arquitetura
- `docs/contrato-dados.md`: formato dos dados trocados entre crawler, API e banco
- `docs/decisoes.md`: decisões tomadas com a parceira e pendências em aberto
- `docs/inventario-sites.md`: como cada Fatec publica seus PPCs
