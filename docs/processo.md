# Registro do processo

Catálogo do que foi feito na montagem do FatecOrg, por que foi feito e o que ficou pendente.
Complementa `decisoes.md` (decisões com a parceira) e `inventario-sites.md` (o que cada site
publica).

## Linha do tempo (12/10/2026)

| # | Branch | O que foi feito |
| --- | --- | --- |
| 1 | `develop` | Esqueleto do monorepo gerado pelo `scripts/bootstrap_monorepo.sh` (Fase 0, tarefa M1) |
| 2 | `develop` | CODEOWNERS só com `@Schinor` e `@leonardoricci-tsi` |
| 3 | `develop` | Projeto Angular em `apps/web` (M4); `ng build` ok |
| 4 | `develop` | Proteção contra vazamento de segredos (ver abaixo) |
| 5 | `chore/fatecorg-e-decisoes` | Sistema renomeado para **FatecOrg**; decisões da parceira; inventário de Pompeia e Marília |
| 6 | `chore/infra-garage` | **Garage** como object storage S3 no lugar do MinIO (M5) |
| 7 | `feat/crawler-pipeline` | Crawler da Fase 1 completo (C2 a C8, C10) |

As branches estão **empilhadas**: cada uma parte da anterior. Os PRs para a `develop` devem ser
mesclados nessa ordem: 5, 6, 7.

## Fase 0: monorepo

### O que o `bootstrap_monorepo.sh` faz

É um script que só **cria arquivos**: não instala nada e não acessa a rede.

1. **Proteção:** `set -euo pipefail` e recusa se a pasta de destino já existir.
2. **Pastas:** `apps/{crawler,api,web}`, `packages/core`, `infra`, `docs`, `data`, `.github`.
3. **Raiz:** `pyproject.toml` com o **uv workspace** (core, crawler, api), Ruff, pytest e pyright,
   mais `.gitignore`, `.editorconfig`, `.env.example`, `Makefile` e `.python-version` (3.12).
   Cada arquivo é escrito com heredoc `<<'EOF'`; as aspas impedem o bash de expandir `$variáveis`.
4. **GitHub:** CI (job `python` com Ruff e pytest; job `web` com `ng build`), CODEOWNERS e
   templates de PR e issue.
5. **`packages/core`:** as entidades Pydantic, que são o contrato de dados.
6. **`apps/crawler`:** `drive.py`, `discover.py` e `cli.py` com código real; os outros módulos
   eram stubs; seed com Pompeia; testes da heurística.
7. **`apps/api`:** FastAPI mínima com `/health`.
8. **`apps/web`, `infra`, `docs`:** README do Angular, Docker Compose, ADR 0001 e contrato de dados.

### Ajustes feitos depois do bootstrap

| Problema | Correção |
| --- | --- |
| O job `web` do CI usava `hashFiles` no `if` do job, o que o GitHub Actions não aceita | `if` removido (o Angular já existe) |
| `data/` com `!data/.gitkeep` não versionava a pasta | Padrão trocado para `data/*` |
| Faltava o marcador `rede` do pytest | Testes com `-m rede` ficam fora do CI |
| O Ruff atual formata blocos de código dentro de `.md` e quebrava o `make lint` por causa dos documentos de planejamento | Os documentos `0*_*.md` ficam fora do Git (`.gitignore`) |
| O CI só rodava na `main` | Roda também na `develop` |

## Segurança: nada sensível no repositório

| Camada | Como funciona |
| --- | --- |
| `.gitignore` | Bloqueia `.env*` (só o `.env.example` passa), chaves (`.pem`, `.key`, `id_rsa*`, `id_ed25519*`), credenciais (`credentials*.json`, `service-account*.json`, `client_secret*.json`), `.npmrc`, `.pypirc`, `.netrc`, `.pgpass`, bancos e dumps locais, logs e `data/` |
| Hook de pre-commit | **gitleaks** (senhas, tokens, chaves), detector de chave privada, bloqueio de arquivos acima de 1 MB e Ruff. Instale uma vez por clone: `uv run pre-commit install` |
| CI | Job `segredos` roda o gitleaks sobre **todo o histórico** em cada PR e push |
| `.env` | Gerado por `make env` com segredos aleatórios e permissão 600. E-mails (contato do crawler, notificações) ficam só nele |
| Fixtures de teste | HTML real **sem `<script>`/`<style>`**: o gitleaks achou uma chave de API do Google embutida nos scripts do Google Sites. Também removemos o parâmetro `ouid` (ID de conta Google) |
| Meta das coletas | Os cabeçalhos salvos em `data/raw/*.meta.json` não incluem `Set-Cookie` |
| Commits | Só na autoria do Marcio, sem linhas de coautoria |

Ainda falta fazer no GitHub: em Settings → Code security, ligar **Secret scanning** e **Push
protection**.

## Decisões

Estão em `decisoes.md`. Em resumo:

- nome do sistema: FatecOrg;
- unidades iniciais: Pompeia e Marília;
- coleta semanal, de madrugada;
- PPC guardado inteiro (os campos específicos ainda serão definidos);
- Marcio recebe as notificações e é o contato do crawler;
- object storage: Garage.

## Infra local (Garage + Postgres)

```bash
make env        # uma vez: cria o .env com segredos aleatórios
make infra-up   # sobe Postgres 16 e Garage v2.4.1 e cria a chave e o bucket "ppcs"
make infra-down
```

- `infra/garage/garage.toml` não tem segredos. `rpc_secret` e `admin_token` vêm das variáveis
  `GARAGE_RPC_SECRET` e `GARAGE_ADMIN_TOKEN` do `.env`.
- O `docker compose` **falha** se faltar algum segredo no `.env`, em vez de usar um valor padrão
  inseguro.
- As portas ficam só em `127.0.0.1`: Postgres na 5432, S3 na 3900 e admin do Garage na 3903.
- `scripts/garage-init.sh` faz o layout de um nó, importa a chave S3 do `.env` e cria o bucket.
  Pode rodar quantas vezes quiser.
- Validado com put/get/delete via boto3 no bucket `ppcs`.

## Fase 1: crawler

O que cada módulo faz está em `apps/crawler/README.md`. Em resumo:

```text
seed → páginas de curso → fetch (robots, 2 s, cache) → discover (pontuação)
     → download (formato, SHA-256) → dedup → data/ppcs/... + texto → ppcs.jsonl / coletas.jsonl
```

### O que os sites mostraram

- **Pompeia (Google Sites):**
  - o PPC fica num iframe do Drive com a URL em `data-src` e o nome no `aria-label`, por isso a
    heurística original não achava nada;
  - o HTML estático basta, sem Playwright (resposta do spike C2);
  - o curso de MAP não publica o PPC.
- **Marília (WordPress do CPS):**
  - não há PPC, só matrizes e ementários (alguns em `.zip`) num Azure Blob do CPS;
  - o crawler passou a classificar `tipo_documento`: `ppc`, `matriz` ou `ementario`.
- **`robots.txt` do Google Drive:**
  - **proíbe o download direto (`/uc`)**;
  - o crawler respeita a regra e registra `erro_drive`;
  - **os PPCs de Pompeia ainda não são baixados**. As opções estão em `decisoes.md`.

### Primeira rodada real

| Rodada | Resultado |
| --- | --- |
| 1ª (`run --todas`, 33 s) | 12 documentos novos de Marília; 2 PPCs de Pompeia bloqueados pelo `robots.txt`; MAP sem PPC |
| 2ª, logo em seguida | 12 `sem_mudanca`: nada duplicado (definição de pronto da C6) |

O `relatorio` mostrou cobertura de 3/6 cursos.

### Testes

- **49 testes no CI:**
  - unitários;
  - snapshots com o HTML real de 4 páginas;
  - HTTP simulado: 200, 304, 429 com retry, 5xx, robots, confirmação do Drive, formatos;
  - pipeline de ponta a ponta com dedup.
- **2 testes marcados `rede`**, que acessam os sites de verdade e só rodam localmente.
- Lint, formatação e pyright sem erros.

## Pendências

| Pendência | Responsável |
| --- | --- |
| Push das branches e PRs na ordem 5 → 6 → 7 | Marcio (a chave SSH tem senha) |
| Decidir o caso do Drive de Pompeia (robots) | Grupo + orientação |
| Definir os campos específicos do PPC (abrir issue) | Grupo + parceira |
| Lista oficial das demais Fatecs do Polo 08 | Parceira |
| Agendamento semanal (C9): onde roda o cron | Marcio + Ígor |
| OCR das matrizes em imagem (C11, opcional) | Marcio |
| Ligar Secret scanning + Push protection; proteção da `main`/`develop`, labels e milestones (M3) | Ígor / Marcio (precisa do `gh`) |
| Fase 2: `RepoSink`, SQLAlchemy + Alembic, storage S3 via Garage | João, Ígor, Marcio |
