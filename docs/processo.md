# Registro do processo

Catálogo do que foi feito na montagem do FatecOrg, por que foi feito e o que ficou pendente.
Complementa `decisoes.md` (decisões com a parceira) e `inventario-sites.md` (o que cada site
publica).

## Estado atual (06/11/2026)

Leia esta seção primeiro ao retomar o projeto.

| Frente | Situação |
| --- | --- |
| Fase 0 (monorepo, CI, segurança) | Pronta. CI verde na `main` e na `develop` (15/10/2026) |
| Infra local (Postgres + Garage) | Pronta e validada (`make infra-up`) |
| Fase 1 (crawler, saída em JSONL) | Pronta: C2 a C8 e C10. 55 testes passando |
| Avisos do Drive | Prontos na branch `feat/crawler-avisos-drive`, **já enviada ao GitHub, mas sem PR** |
| API (`apps/api`) | Só o `/health` |
| Front-end (`apps/web`) | Projeto Angular gerado, sem telas |
| Fase 2 (banco + storage) | **Em andamento** na `feat/core-persistencia`: itens 1 a 3 do plano prontos (tabelas, Alembic, repositórios e storage) |

Branches: `main` e `develop` estão iguais (`5c922ec`). Abertas:

- `feat/crawler-avisos-drive`: PR #1 para a `develop`, aguardando revisão;
- `feat/core-persistencia`: parte da anterior, porque usa o modelo `Aviso`. Depois do merge do
  PR #1, rebase na `develop` (`git rebase develop`) e abra o PR.

No GitHub:

- Secret scanning e Push protection estão **ligados**;
- a `main` e a `develop` **não têm proteção de branch**;
- não há labels de módulo nem milestones.

A última coleta real é de 12/10/2026. O `data/avisos.json` só aparece no próximo
`fatecorg-crawler run`.

### Para retomar

1. Revisar e mesclar o PR #1 (squash).
2. Rebase da `feat/core-persistencia` na `develop` e abrir o PR dela.
3. Seguir o plano da Fase 2 abaixo, a partir do item 4.

### Plano da Fase 2: persistência

O objetivo é destravar a API (João) e o front-end (Amabili). Ordem sugerida, um PR por item:

1. ✅ **Modelos SQLAlchemy** em `packages/core/db/tabelas.py`: `unidade`, `curso`, `ppc_versao` (`campos` em
   JSONB, vazio por enquanto), `coleta` e `aviso`. A identidade de `ppc_versao` é
   `(unidade, curso, sha256)`, igual ao dedup da Fase 1.
2. ✅ **Alembic** com a primeira migration (`infra/migrations/versions/..._0001_...`). Testada num
   Postgres descartável: sobe, desce e não diverge das tabelas (`alembic check`). O CI agora tem
   um Postgres de serviço só para esse teste (`TEST_DATABASE_URL`).
3. ✅ **Repositórios** (`packages/core/repositories`) e **storage** (`packages/core/storage`).
   A chave no Garage é a mesma do `caminho_local`: `ppcs/<unidade>/<curso>/<sha256>.<formato>`.
   - `CatalogoRepo` espelha o seed (cria e atualiza, nunca apaga); `VersaoRepo`, `ColetaRepo` e
     `AvisoRepo` recebem e devolvem entidades de `domain`, não linhas do banco;
   - `AvisoRepo.atualizar` segue a mesma regra do `data/avisos.json`;
   - `S3Storage` (Garage, `S3_*` do `.env`) e `LocalStorage` (pasta, usada nos testes);
   - testes em SQLite e S3 simulado (moto). Validado também à mão num Postgres e num Garage
     descartáveis.
4. **`RepoSink`** no crawler, com a mesma interface do `Sink` e escolhido por configuração.
   O `JsonlSink` continua sendo o padrão nos testes.
5. **Importação** do que já está em `data/*.jsonl` e `data/avisos.json`, para não perder a primeira
   coleta.
6. **API:** `GET /avisos`, listagem de PPCs por unidade e curso, e upload manual (é a saída provável
   para os PPCs de Pompeia).

Depois disso: agendamento semanal (C9) e o banner de avisos no Angular.

### Decisões do banco (06/11/2026)

- Enums guardados como **texto com CHECK**, não como tipo nativo do Postgres: incluir um valor
  novo (ex.: outro `TipoAviso`) é só mudar o CHECK na migration.
- `ppc_versao.origem` distingue `crawler` de `upload` (o upload manual da API).
- `aviso` guarda o histórico: um aviso resolvido ganha `resolvido_em` e continua no banco. Um
  índice único parcial garante só um aviso **aberto** por documento.
- `coleta.curso_id` é nulo quando a falha foi na home da unidade (na Fase 1, `curso_slug = "-"`).
- Repositórios não abrem transação: quem chama usa `with sessao(engine) as s:` e decide o commit.
- Os testes das tabelas rodam em SQLite (rápidos); o das migrations precisa de Postgres
  (`@pytest.mark.postgres`) e é pulado sem `TEST_DATABASE_URL`.

## Linha do tempo (12/10 a 14/10/2026)

| # | Branch | O que foi feito |
| --- | --- | --- |
| 1 | `develop` | Esqueleto do monorepo gerado pelo `scripts/bootstrap_monorepo.sh` (Fase 0, tarefa M1) |
| 2 | `develop` | CODEOWNERS só com `@Schinor` e `@leonardoricci-tsi` |
| 3 | `develop` | Projeto Angular em `apps/web` (M4); `ng build` ok |
| 4 | `develop` | Proteção contra vazamento de segredos (ver abaixo) |
| 5 | `chore/fatecorg-e-decisoes` | Sistema renomeado para **FatecOrg**; decisões da parceira; inventário de Pompeia e Marília |
| 6 | `chore/infra-garage` | **Garage** como object storage S3 no lugar do MinIO (M5) |
| 7 | `feat/crawler-pipeline` | Crawler da Fase 1 completo (C2 a C8, C10) |
| 8 | `feat/crawler-avisos-drive` | Avisos de documento bloqueado no Drive, com notificação por e-mail (14/10/2026) |
| 9 | `feat/core-persistencia` | Fase 2: tabelas SQLAlchemy, Alembic e Postgres no CI (06/11/2026) |

As branches 5 a 7 estavam empilhadas e já estão todas na `main` (e a `develop` foi atualizada
para a `main` em 14/10/2026). Daqui em diante, cada branch de tarefa sai da `develop`.

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

### Avisos do Drive (14/10/2026)

Decisão em `decisoes.md`. Ao fim de cada `run`, o crawler transforma as coletas `erro_drive`
causadas pelo `robots.txt` em avisos `drive_bloqueado`:

- `data/avisos.json` guarda os avisos **abertos** (um por unidade, curso e arquivo), com
  `detectado_em` (primeira rodada) e `visto_em` (última);
- um aviso **novo** é notificado uma vez: no terminal e, se `NOTIFICACAO_SMTP_HOST` e
  `NOTIFICACAO_DESTINATARIOS` estiverem no `.env`, por e-mail. Nas semanas seguintes ele continua
  aberto, mas não gera e-mail de novo;
- o aviso fecha quando a página do curso é lida e o bloqueio some. Erro de rede não fecha;
- `fatecorg-crawler avisos` lista os abertos por unidade e alerta quando há mais de uma unidade
  com o problema (gatilho para mapear a solução);
- Fase 2: o `RepoSink` grava os avisos numa tabela, a API expõe `GET /avisos` e o Angular mostra
  um banner na página da unidade/curso. O formato está em `contrato-dados.md`.

Com os dados reais, os avisos abertos são os 2 PPCs de Pompeia (Sistemas Inteligentes e Big Data
no Agronegócio).

### Testes

- **55 testes no CI** (49 da Fase 1 e 6 dos avisos):
  - unitários;
  - snapshots com o HTML real de 4 páginas;
  - HTTP simulado: 200, 304, 429 com retry, 5xx, robots, confirmação do Drive, formatos;
  - pipeline de ponta a ponta com dedup.
- **2 testes marcados `rede`**, que acessam os sites de verdade e só rodam localmente.
- Lint, formatação e pyright sem erros.

## Pendências

| Pendência | Responsável |
| --- | --- |
| PR da `feat/crawler-avisos-drive` para a `develop` (o push já foi feito) | Marcio |
| Fase 2: persistência (plano em "Estado atual") | João, Ígor, Marcio |
| Configurar o SMTP no `.env` para os avisos chegarem por e-mail | Marcio |
| Banner de avisos no front-end (depende do `GET /avisos` da Fase 2) | Amabili + João |
| Solução definitiva para o Drive, se outra Fatec tiver o mesmo bloqueio | Grupo + orientação |
| Definir os campos específicos do PPC (abrir issue) | Grupo + parceira |
| Lista oficial das demais Fatecs do Polo 08 | Parceira |
| Agendamento semanal (C9): onde roda o cron | Marcio + Ígor |
| OCR das matrizes em imagem (C11, opcional) | Marcio |
| A porta 5432 local está ocupada por outro projeto (`prf_postgres`): pare-o antes do `make infra-up` ou mude a porta no compose | Marcio |
| Proteção da `main`/`develop`, labels e milestones (M3). Secret scanning e Push protection já estão ligados | Ígor / Marcio (com o `gh`) |
