# Segurança: pentest e correções

Registro do pentest do FatecOrg, do que foi corrigido e do que ficou pendente. Atualize a cada
rodada: novas linhas nas tabelas, sem apagar as antigas.

## Rodada 1 (06/11/2026)

### Escopo e regras

- **Alvo:** API (`apps/api`), crawler (`apps/crawler`), domínio e storage (`packages/core`),
  dependências Python e do Angular (`apps/web`), configuração do repositório no GitHub.
- **Ambiente:** só local. Postgres, Garage e API **descartáveis**, em portas altas (55432,
  53900, 58000), com segredos aleatórios gerados na hora. Os dados são os da primeira coleta
  (`data/`), importados com `fatecorg-crawler importar`. Nada do `.env` ou do compose foi usado.
- **Não destrutivo:** nenhum site das Fatecs foi atacado. O comportamento do crawler foi testado
  com respostas simuladas (`httpx.MockTransport`).

### Ferramentas

| Ferramenta | Para quê |
| --- | --- |
| `pip-audit` | CVEs conhecidas nas dependências Python (`uv export`) |
| `npm audit` | CVEs nas dependências do Angular |
| `bandit` | Análise estática do código Python |
| `gitleaks` (pre-commit e CI) | Segredos no histórico |
| `scripts/pentest-local.sh` | Testes dinâmicos contra a API rodando (curl e Python) |
| Leitura de código | Autenticação, validação de entrada, redirects, limites de tamanho |

### Achados

Severidade: **Alta** (explorável sem credencial, impacto real), **Média** (exige condição
específica ou afeta disponibilidade), **Baixa** (endurecimento), **Info** (registro).

| ID | Severidade | Achado | Status |
| --- | --- | --- | --- |
| A-1 | **Alta** | `POST /ppcs` sem token: o servidor recebia o corpo inteiro (testado com 300 MB) antes de responder 401. Qualquer pessoa podia encher o disco temporário e gastar banda | ✅ Corrigido |
| A-2 | Média | `GET /ppcs?deslocamento=10^21` derrubava a consulta com erro 500 (`bigint out of range`) | ✅ Corrigido |
| A-3 | Média | Com o Garage fora do ar, o download ficava preso por mais de 60 s (timeouts padrão do boto3); muitas requisições assim esgotam os workers | ✅ Corrigido |
| A-4 | Média | Não há limite de requisições: 300 consultas seguidas, todas 200 | ⏳ Pendente (proxy) |
| A-5 | Baixa | `/docs` e `/openapi.json` públicos | ✅ Configurável (`API_DOCS=false`) |
| A-6 | Baixa | Cabeçalho `server: uvicorn` revela o servidor | ⏳ Pendente (deploy) |
| A-7 | Baixa | Upload com **um** token compartilhado: não dá para saber quem enviou nem revogar uma pessoa | ⏳ Aceito por ora |
| A-8 | Info | O campo `titulo` do upload volta no JSON como veio. O Angular escapa por padrão; nunca usar `innerHTML` ou `bypassSecurityTrust*` com ele | 📌 Regra para o front; seguida nas telas de 07/11 e coberta por teste (`avisos-banner.spec.ts`) |
| C-1 | Média | O crawler seguia redirects sem conferir o destino: um site (ou link) podia levá-lo a `127.0.0.1`, à rede interna ou a `169.254.169.254` (metadados de nuvem), e a caminhos proibidos pelo `robots.txt` | ✅ Corrigido |
| C-2 | Média | Respostas eram lidas inteiras na memória, sem limite de tamanho | ✅ Corrigido |
| C-3 | Baixa | A URL do formulário de confirmação do Drive era seguida sem validar o domínio | ✅ Corrigido |
| D-1 | Média | `certifi` 2026.7.22 com 2 CVEs (usado em runtime pelo httpx e pelo boto3) | ✅ Atualizado |
| D-2 | Baixa | `filelock` e `virtualenv` com CVEs (só desenvolvimento, via pre-commit) | ✅ Atualizados |
| D-3 | Baixa | 8 vulnerabilidades no ferramental do Angular (Vite, Vitest, CLI, zod, undici). Nenhuma no bundle de produção | ✅ `npm audit`: 0 |
| E-1 | Info | `bandit`: SHA1 para nome de arquivo de cache (não é uso criptográfico) e um `assert` na CLI | ✅ Ajustados |
| G-1 | Média | GitHub: `main` e `develop` sem proteção de branch; Dependabot desligado | ⏳ Pendente (M3) |

**O que resistiu**, sem achado:

- **Autenticação do upload:** sem header, `Bearer` vazio, esquema `Basic` e token na query
  recebem 401. `bearer` minúsculo é aceito, como manda a RFC 6750.
- **Travessia de caminho:** `..%2F` em slug e SHA recebem 404 ou 422, por causa das regex.
- **SQL injection** na query: 422. Os repositórios usam o ORM com parâmetros.
- **PDF com 20 mil páginas** (2,4 MB): extraído em cerca de 1 s.
- **CORS:** só a origem configurada recebe `Access-Control-Allow-Origin`.
- **Cabeçalhos de download:** o nome do arquivo é montado com slug, enum e SHA já validados, então
  não há injeção.

### Correções

| ID | O que mudou | Onde | Teste |
| --- | --- | --- | --- |
| A-1 | Middleware confere o token e o `Content-Length` **antes** de ler o corpo; a dependência da rota continua como segunda barreira | `apps/api/.../main.py`, `deps.py` | `test_a1_*` (corpo que falha se for lido) |
| A-2 | `deslocamento` limitado a 100 000 | `rotas/ppcs.py` | `test_a2_*` |
| A-3 | S3 com `connect_timeout=5`, `read_timeout=10` e 2 tentativas; erro do storage vira 503 genérico, sem endereço interno | `packages/core/.../storage`, `main.py` | `test_a3_*` |
| A-5 | `API_DOCS=false` desliga `/docs`, `/redoc` e `/openapi.json` | `config.py` | `test_a5_*` |
| C-1 | Hook em **toda** requisição, inclusive redirects: bloqueia IP interno (literal ou por DNS) e confere o `robots.txt` do destino | `apps/crawler/.../fetch.py` | `test_c1_*` |
| C-2 | Leitura em blocos com limite `CRAWLER_MAX_MB_RESPOSTA` (padrão 100) | `fetch.py` | `test_c2_*` |
| C-3 | Formulário do Drive só para `drive.google.com`, `drive.usercontent.google.com` ou `docs.google.com` | `download.py` | `test_c3_*` |
| D-1..3 | `uv lock --upgrade-package ...`; `npm audit fix` e `npm update` (Angular 22.2.5, Vite 8.3.5) | `uv.lock`, `apps/web/package-lock.json` | `pip-audit` e `npm audit` sem achados; `ng build` ok |
| E-1 | `sha1(..., usedforsecurity=False)`; `assert` trocado por erro da CLI | `fetch.py`, `cli.py` | `bandit` sem achados |

Reteste no mesmo ambiente descartável, depois das correções:

- 300 MB sem token: **401 com 0 bytes recebidos**;
- `deslocamento` gigante: **422**;
- Garage pausado: **503 em segundos**, com a mensagem genérica.

### Pendências (para o deploy)

| ID | O que fazer | Responsável |
| --- | --- | --- |
| A-4 | Limite de requisições no proxy reverso (ex.: nginx `limit_req` por IP, mais rígido no `POST /ppcs`) | Ígor |
| A-5 | Em produção, `API_DOCS=false` ou `/docs` só pela rede interna | Ígor |
| A-6 | `uvicorn --no-server-header` e HTTPS no proxy (HSTS) | Ígor |
| A-7 | Antes de abrir o upload para mais gente: um token por pessoa (ou login), com registro de quem enviou | João + Marcio |
| A-8 | Revisar no PR do front que `titulo` e `mensagem` só são exibidos com interpolação (`{{ }}`) | Amabili |
| G-1 | Proteção de `main`/`develop` (PR obrigatório, CI verde) e Dependabot ligado | Marcio (com o `gh`) |

### Rotas novas depois da rodada 1 (07/11/2026)

Revisadas ao serem criadas; entram no escopo da próxima rodada do pentest.

| Rota | Cuidado tomado |
| --- | --- |
| `GET /busca` | `q` de 2 a 200 caracteres e no máximo 50 resultados; a consulta vai como parâmetro para o `websearch_to_tsquery`, sem SQL montado à mão. Os trechos voltam como dados (`texto`, `destaque`), nunca HTML (A-8) |
| `GET /ppcs/{u}/{c}/comparar` | Comparar custa CPU: textos acima de 60 mil palavras são recusados (o maior real tem 20 mil) e o resultado fica em cache (o texto de uma versão nunca muda). Só compara versões do mesmo curso |

O limite de requisições do proxy (A-4) vale também para elas e é o que impede abuso em volume.

### Como repetir

```bash
bash scripts/pentest-local.sh        # precisa do Docker e de data/ com a primeira coleta
uvx pip-audit -r <(uv export --all-packages --no-hashes --no-emit-workspace --frozen -q)
uvx bandit -q -r apps/api/src apps/crawler/src packages/core/src
(cd apps/web && npm audit)
```

O script usa portas altas e containers próprios (`fatecorg-pg-teste`, `fatecorg-garage-teste`)
e os remove no fim. Os testes de regressão de cada achado estão em
`apps/api/tests/test_seguranca.py` e `apps/crawler/tests/test_seguranca.py` e rodam no CI.
