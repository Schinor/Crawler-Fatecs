# Registro do processo

Catálogo do que foi feito na montagem do FatecOrg, por que foi feito e o que ficou pendente.
Complementa `decisoes.md` (decisões com a parceira) e `inventario-sites.md` (o que cada site
publica).

## Estado atual (08/11/2026)

Leia esta seção primeiro ao retomar o projeto.

| Frente | Situação |
| --- | --- |
| Fase 0 (monorepo, CI, segurança) | Pronta. CI verde na `main` e na `develop` (15/10/2026) |
| Infra local (Postgres + Garage) | Pronta e validada (`make infra-up`) |
| Fase 1 (crawler, saída em JSONL) | Pronta: C2 a C8 e C10. 55 testes passando |
| Agendamento semanal (C9) | Scripts prontos na `feat/crawler-agendamento` (`make agendar`); falta escolher a máquina e registrar as duas rodadas automáticas |
| Avisos do Drive | Prontos na branch `feat/crawler-avisos-drive`, **já enviada ao GitHub, mas sem PR** |
| API (`apps/api`) | Consulta de unidades, versões e avisos, download, busca, comparação, login com perfis (A1) e upload manual autenticado |
| Front-end (`apps/web`) | Telas de unidades, histórico, documentos, busca, comparação, upload e login (W1), com o banner de avisos |
| Segurança | Pentest local da rodada 1 feito e corrigido (`docs/seguranca.md`), na `fix/seguranca-pentest`; pendências de deploy listadas lá |
| Fase 2 (banco + storage) | **Em andamento** na `feat/core-persistencia`: **itens 1 a 6 prontos**: o crawler grava no Postgres + Garage (`--sink banco`) e a API consulta, baixa e recebe upload |

Branches: `main` e `develop` estão iguais (`5c922ec`). Abertas:

- `feat/crawler-avisos-drive`: PR #1 para a `develop`, aguardando revisão;
- `feat/core-persistencia`: parte da anterior, porque usa o modelo `Aviso`. Depois do merge do
  PR #1, rebase na `develop` (`git rebase develop`) e abra o PR;
- `fix/seguranca-pentest`: parte da `feat/core-persistencia`. Mesma regra: PR depois dela;
- `feat/crawler-agendamento`: parte da `fix/seguranca-pentest` (C9). PR depois dela;
- `feat/web-telas`: parte da `feat/crawler-agendamento` (telas do Angular). PR depois dela;
- `feat/busca-comparacao`: parte da `feat/web-telas` (busca e comparação). PR depois dela;
- `feat/auth-login`: parte da `feat/busca-comparacao` (login, A1/W1). PR depois dela.

No GitHub:

- Secret scanning e Push protection estão **ligados**;
- a `main` e a `develop` **não têm proteção de branch**;
- não há labels de módulo nem milestones.

A última coleta real é de 07/11/2026, feita pelo `scripts/coleta-semanal.sh` em 33 s: os mesmos
12 documentos de Marília (`sem_mudanca`) e os 2 avisos do Drive de Pompeia, agora em
`data/avisos.json`.

### Para retomar

1. Revisar e mesclar o PR #1 (squash).
2. Rebase da `feat/core-persistencia` na `develop` e abrir o PR dela.
3. Agendar a coleta (`make agendar`) na máquina escolhida e conferir as duas primeiras rodadas
   (`make agendamento`). Isso fecha a definição de pronto da C9.
4. Revisar as telas com a Amabili (`feat/web-telas` e `feat/busca-comparacao`).
5. No banco de cada ambiente: `make migrate` (migrations 0002 e 0003) e depois
   `uv run fatecorg-crawler indexar`, para as versões antigas entrarem na busca. Antes do deploy,
   resolver as pendências de `docs/seguranca.md`.
6. Para o upload voltar a funcionar: acrescentar `API_JWT_SEGREDO` ao `.env`
   (`openssl rand -hex 32`) e criar o primeiro acesso:
   `make usuario E=<email> N="<nome>" P=admin_polo`.
7. Relatórios (A7/W5) dependem de a parceira definir eixo tecnológico, situação do curso
   (ativo/extinto) e o que "período" significa: nada disso existe nos dados hoje
   (`docs/decisoes.md`).

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
4. ✅ **`RepoSink`** no crawler (`sink.py`): metadados no Postgres, arquivos no Garage. Escolha
   por `--sink banco` ou `CRAWLER_SINK=banco` no `.env`; o padrão continua `jsonl`.
   - O `Sink` agora também guarda os arquivos (`guardar_arquivo`) e cuida dos avisos
     (`atualizar_avisos`, `avisos_abertos`). O pipeline não escreve mais direto em `data/`;
   - a extração de texto lê o PDF da memória, então nada vai para o disco com o `RepoSink`;
   - uma transação por operação: uma falha no meio da rodada não desfaz o que já foi gravado.
5. ✅ **Importação**: `fatecorg-crawler importar` copia `data/` para o banco e o Garage e pode
   rodar mais de uma vez (versões por SHA, coletas só as mais novas que as do banco, avisos
   abertos). Testado com os dados reais num Postgres e num Garage descartáveis: 12 versões,
   30 coletas e 21 arquivos (12 documentos + 9 textos); a 2ª rodada não duplicou nada.

   Para usar no seu ambiente: `make infra-up`, `make migrate`, `uv run fatecorg-crawler importar`
   e, daí em diante, `uv run fatecorg-crawler run --todas --sink banco`.
6. ✅ **API** (`apps/api`). Rotas na tabela abaixo; documentação interativa em `/docs`.
   - O upload manual é a saída para os PPCs do Drive de Pompeia: ao receber o documento, fecha
     os avisos abertos do curso para o mesmo tipo de documento;
   - testes com SQLite e storage local; validado também de ponta a ponta (Postgres + Garage
     descartáveis, dados reais importados, `uvicorn` e `curl`).

   | Rota | O que faz |
   | --- | --- |
   | `GET /unidades` | Unidades e cursos |
   | `GET /ppcs?unidade=&curso=&limite=&deslocamento=` | Versões, da mais recente para a mais antiga (até 200 por página) |
   | `GET /ppcs/{unidade}/{curso}/{sha256}` | Uma versão |
   | `GET /ppcs/{unidade}/{curso}/{sha256}/arquivo` e `/texto` | Download do documento e do texto extraído |
   | `GET /avisos?unidade=&curso=` | Avisos abertos (banner do front-end) |
   | `POST /ppcs` | Upload manual (multipart: `unidade`, `curso`, `tipo_documento`, `titulo`, `arquivo`). Desde 08/11, exige login (ver "Login com perfis") |

Depois disso: agendamento semanal (C9, ver abaixo) e o banner de avisos no Angular.

### Agendamento semanal (C9, 07/11/2026)

A frequência foi decidida com a parceira: domingo às 03h. O cron do GitHub Actions foi
descartado porque não guarda `data/` entre as execuções e não alcança o banco local. A coleta
roda numa máquina do grupo (ou da Fatec, no deploy):

- `scripts/agendar.sh` instala um **timer do systemd do usuário** (`Persistent=true`: uma rodada
  perdida com a máquina desligada acontece quando ela ligar) ou, sem systemd, uma linha no cron.
  `mostrar` exibe o que seria instalado sem mudar nada;
- `scripts/coleta-semanal.sh` faz uma rodada por vez (`flock`) e grava o log em `data/logs/`,
  guardando os 12 mais recentes;
- `run` agora sai com o **código 2** quando nenhuma página foi lida. Uma rodada sem rede não
  passa mais como sucesso;
- em qualquer falha, `fatecorg-crawler notificar-falha` manda por e-mail o fim do log. Antes do
  envio, os valores de variáveis com `SENHA`, `PASSWORD`, `SECRET`, `TOKEN`, `KEY` ou
  `DATABASE_URL` no nome, e senhas dentro de URLs, viram `***`;
- testes: 13 novos (`test_agendamento.py`), inclusive dos scripts de shell com um `uv` falso:
  trava, rotação, código de saída e notificação.

Falta, para a definição de pronto: escolher a máquina, rodar `make agendar` e conferir duas
rodadas automáticas no `coletas.jsonl` (ou na tabela `coleta`).

### Telas do Angular (07/11/2026)

Primeira versão do front-end sobre a API que já existe (detalhes em `apps/web/README.md`):

- **Telas:** unidades (com o selo "precisa de ação"), histórico do curso, documentos com filtro
  e upload manual. O banner de avisos leva ao formulário de envio já preenchido;
- **Contrato (W2):** `scripts/exportar-openapi.py` grava `apps/web/openapi.json` e
  `npm run api:tipos` gera os tipos TypeScript. O CI confere os dois, então uma mudança na API
  sem regenerar quebra o build;
- **Sem CORS:** o `ng serve` repassa `/api` para o uvicorn (`proxy.conf.json`); em produção, o
  proxy reverso faz o mesmo;
- **Versões:** o histórico agrupa por documento (mesmo link de origem). As matrizes A31, B31 e
  C31 de Marília são documentos diferentes, não versões umas das outras;
- **Sem Angular Material por ora:** HTML semântico e CSS próprio (81 KB transferidos na carga
  inicial). A troca continua aberta para a Amabili;
- **Testes:** 17 no Vitest (componentes com `HttpTestingController`, inclusive o A-8). O CI
  agora roda `ng test` e `prettier --check`, além do `ng build`;
- **Validação de ponta a ponta:** API descartável (SQLite + storage local, dados reais
  importados), `ng serve` e Chrome headless em 1280 e 375 px. Nenhuma tela passa de 375 px,
  nenhum erro no console. O upload pelo banner funcionou: token errado recusado, documento
  recebido e aviso do curso fechado.

Fica para depois: relatórios e a auditoria com axe e leitor de tela (W6). A busca, a comparação
e o login vieram logo depois (ver abaixo).

### Busca no conteúdo e comparação entre versões (07/11/2026)

- **Busca (A3):** `GET /busca?q=` procura no título e no texto extraído, com a sintaxe de busca
  na web (`"frase"`, `-palavra`, `or`). No Postgres, usa um índice GIN com a configuração
  `fatecorg_pt` (`portuguese` + `unaccent`): "estagio" acha "estágio", e "estagios" também.
  Os trechos destacados vêm do `ts_headline`, mas a API os devolve como dados, não HTML;
- **Texto no banco:** coluna `ppc_versao.texto` (migration 0002). O `RepoSink` e o upload gravam
  o texto ao registrar a versão; `fatecorg-crawler indexar` preenche as versões antigas;
- **SQLite:** os testes rodam a mesma busca em Python (`fatecorg_core.busca`), sem índice;
- **Comparação (A5):** `GET /ppcs/{u}/{c}/comparar?de=&para=`. A unidade é a linha lógica (as
  quebras que o PDF fez no meio da frase são desfeitas). Pouca mudança aparece palavra por
  palavra; trecho reescrito aparece inteiro, antes e depois. Comparar por parágrafo foi testado
  e descartado: num ementário, um "parágrafo" do PDF é quase uma página;
- **Telas:** `/busca` e `/unidades/:u/cursos/:c/comparar`, com link no histórico do curso;
- **Validação com dados reais** num Postgres descartável: busca em cerca de 130 ms ("gestao de
  pessoas" acha os 4 ementários de gestão, com "Gestão" e "Pessoas" destacados) e uso do índice
  confirmado com `EXPLAIN`. Os ementários C75 e M75 de Gestão Comercial têm só 31 linhas em
  comum: o M75 foi reescrito, e a tela mostra 22 trechos lado a lado em 0,2 s;
- **Testes:** 140 em Python (2 deles no Postgres, no CI) e 26 no Angular;
- o `alembic check` ignora o índice de expressão (`infra/migrations/env.py`), que o autogenerate
  não sabe comparar.

### Login com perfis (A1/W1, 08/11/2026)

Consulta e download continuam públicos; o login é para quem envia documentos. Detalhes de
segurança em `seguranca.md`.

- **Perfis:** `coordenador` envia só para a própria unidade; `admin_polo`, para qualquer uma;
  `consulta` entra, mas não envia;
- **Rotas:** `POST /auth/login`, `/auth/refresh` (204 para visitante) e `/auth/logout`. `POST /ppcs`
  agora exige login, e o token compartilhado `API_TOKEN_UPLOAD` foi removido (A-7);
- **Contas:** só pela linha de comando (`make usuario`, `uv run fatecorg-api redefinir-senha`). O
  cadastro pela tela entra com o Admin (W5);
- **Banco:** migration 0003 (`usuario`, `sessao_login`, `ppc_versao.enviado_por_id`);
- **Front:** `core/auth.ts` guarda o token só na memória e restaura a sessão pelo cookie ao
  recarregar; o interceptor renova e repete quando o token vence; `/enviar` tem guarda de rota e
  devolve à página de origem depois do login, com o formulário do banner preenchido;
- **Validação de ponta a ponta:** Postgres descartável (migrations subindo, descendo e
  `alembic check`), `ng serve` e Chrome headless em 1280 e 375 px: login, senha errada, cookie
  `HttpOnly`/`Secure`/`Strict` pelo proxy, upload com autor gravado, sessão mantida ao recarregar,
  logout. Nenhuma tela passa de 375 px e o único erro no console é o 401 da senha errada;
- **Testes:** 166 em Python e 44 no Angular.

### Decisões do banco (06/11/2026)

- Enums guardados como **texto com CHECK**, não como tipo nativo do Postgres: incluir um valor
  novo (ex.: outro `TipoAviso`) é só mudar o CHECK na migration.
- `ppc_versao.origem` distingue `crawler` de `upload` (o upload manual da API).
- `aviso` guarda o histórico: um aviso resolvido ganha `resolvido_em` e continua no banco. Um
  índice único parcial garante só um aviso **aberto** por documento.
- `coleta.curso_id` é nulo quando a falha foi na home da unidade (na Fase 1, `curso_slug = "-"`).
- **Segurança da API:**
  - o upload exige token, comparado em tempo constante. Sem `API_TOKEN_UPLOAD` no `.env`, o
    upload fica desligado (503);
  - limite de tamanho (`API_MAX_UPLOAD_MB`, padrão 50) e formato validado pela assinatura do
    arquivo, não pela extensão;
  - slugs e SHA validados por regex (bloqueia `../`);
  - CORS só para `API_CORS_ORIGENS`;
  - cabeçalhos `nosniff` e `no-referrer`;
  - a resposta não expõe as chaves do storage.
  Consulta e download são públicos, porque os documentos já são públicos nos sites das Fatecs.
- Detecção de formato e extração de texto foram para `packages/core/arquivos.py`, para que o
  crawler e o upload gravem igual.
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
| 9 | `feat/core-persistencia` | Fase 2: tabelas, Alembic, repositórios, storage S3, `RepoSink`, importação e API (06/11/2026) |
| 10 | `fix/seguranca-pentest` | Pentest local, 11 correções com teste de regressão e dependências sem CVE (06/11/2026) |
| 11 | `feat/crawler-agendamento` | Coleta semanal agendada (C9): timer do systemd ou cron, log, trava e e-mail de falha (07/11/2026) |
| 12 | `feat/web-telas` | Telas do Angular (unidades, histórico, documentos, upload, banner de avisos) e contrato OpenAPI no CI (07/11/2026) |
| 13 | `feat/busca-comparacao` | Busca full-text em português sem acento (A3) e comparação entre versões (A5), com as telas (07/11/2026) |
| 14 | `feat/auth-login` | Login com perfis, refresh rotativo e upload autenticado com registro do autor (A1/W1, A-7) (08/11/2026) |

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
| Revisar as telas do Angular (`feat/web-telas`); decidir se entra o Angular Material | Amabili |
| Rodar `make migrate` e `fatecorg-crawler indexar` em cada banco já existente (busca) | Marcio / Ígor |
| Solução definitiva para o Drive, se outra Fatec tiver o mesmo bloqueio | Grupo + orientação |
| Definir os campos específicos do PPC (abrir issue) | Grupo + parceira |
| Lista oficial das demais Fatecs do Polo 08 | Parceira |
| Agendamento semanal (C9): escolher a máquina, rodar `make agendar` e conferir 2 rodadas automáticas | Marcio + Ígor |
| OCR das matrizes em imagem (C11, opcional) | Marcio |
| Acrescentar `API_JWT_SEGREDO` ao `.env` local (`openssl rand -hex 32`) e criar o primeiro admin (`make usuario`); o `make env` já gera o segredo para clones novos | Marcio |
| Definir com a parceira eixo, situação do curso e período: destrava os relatórios (A7/W5) | Grupo + parceira |
| Pendências de deploy do pentest (limite de taxa, HTTPS, `/docs`, proteção de branch) | Ígor + Marcio (ver `docs/seguranca.md`) |
| A porta 5432 local está ocupada por outro projeto (`prf_postgres`): pare-o antes do `make infra-up` ou mude a porta no compose | Marcio |
| Proteção da `main`/`develop`, labels e milestones (M3). Secret scanning e Push protection já estão ligados | Ígor / Marcio (com o `gh`) |
