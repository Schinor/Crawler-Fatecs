# Contrato de dados

Fonte da verdade: `packages/core/src/fatecorg_core/domain/models.py`. Mudanças passam por PR com
revisão do CODEOWNERS e atualizam este arquivo.

## Seed: `apps/crawler/seeds/unidades.yaml`

`Unidade` (`slug`, `nome`, `cidade`, `site_url`, `plataforma`, `ativa`) com uma lista de
`CursoSeed` (`slug`, `nome`, `url` da página do curso).

## Saída do crawler (Fase 1, antes do banco)

### `data/ppcs.jsonl`: uma linha `PPCEncontrado` por versão nova de documento

| Campo | Descrição |
| --- | --- |
| `unidade_slug`, `curso_slug`, `curso_nome` | De onde veio |
| `tipo_documento` | `ppc`, `matriz` ou `ementario` |
| `pagina_url`, `arquivo_url`, `titulo_link` | Página do curso, link do arquivo e rótulo do link |
| `formato` | `pdf`, `doc`, `docx`, `odt` ou `zip` (detectado pelo conteúdo) |
| `sha256`, `tamanho_bytes` | Identidade da versão |
| `caminho_local` | `ppcs/<unidade>/<curso>/<sha256>.<formato>`, relativo a `data/` (mesma chave no Garage na Fase 2) |
| `caminho_texto`, `paginas`, `precisa_ocr` | Texto extraído (só PDF) |
| `coletado_em` | Data e hora UTC |

### `data/coletas.jsonl`: uma linha `Coleta` por resultado de cada rodada

`unidade_slug`, `curso_slug`, `curso_nome`, `iniciada_em`, `status` e `detalhe` (URL, tipo,
SHA ou erro). Status: `novo_ppc`, `sem_mudanca`, `sem_ppc`, `erro_http`, `erro_drive`, `nao_pdf`.

### `data/avisos.json`: lista dos `Aviso` abertos (estado atual, reescrito a cada rodada)

| Campo | Descrição |
| --- | --- |
| `tipo` | Hoje só `drive_bloqueado` (o `robots.txt` do Drive proíbe o download) |
| `unidade_slug`, `curso_slug`, `curso_nome`, `tipo_documento` | Onde está o documento |
| `pagina_url`, `arquivo_url`, `titulo_link` | Página do curso e link do documento bloqueado |
| `mensagem` | Texto pronto para o front-end exibir |
| `detectado_em`, `visto_em` | Primeira e última rodada em que o aviso estava aberto (UTC) |

Identidade: `(unidade_slug, curso_slug, arquivo_url)`. Na Fase 2 vira a tabela `aviso`, exposta
pela API em `GET /avisos` (filtros `unidade` e `curso`) para o banner do Angular.

## Banco (Fase 2)

Fonte da verdade: `packages/core/src/fatecorg_core/db/tabelas.py`. Toda mudança gera uma migration
(`make migration M="..."`) revisada no PR.

| Tabela | Conteúdo | Identidade |
| --- | --- | --- |
| `unidade` | Fatec do seed | `slug` |
| `curso` | Curso de uma unidade, com a página onde publica os documentos | `(unidade_id, slug)` |
| `ppc_versao` | Uma versão de documento (PPC, matriz ou ementário), vinda do crawler ou de upload. `chave_arquivo` é a chave no Garage; `texto` guarda o texto extraído (índice full-text `ix_ppc_versao_busca`, configuração `fatecorg_pt`: português sem acento); `campos` (JSONB) fica vazio por enquanto | `(curso_id, sha256)` |
| `coleta` | Log de cada resultado de cada rodada (`curso_id` nulo = falha na home) | `id` |
| `aviso` | Avisos para o front-end; os resolvidos ficam com `resolvido_em` | um aberto por `(curso_id, arquivo_url)` |

## API (Fase 2)

Documentação interativa em `http://localhost:8000/docs` (OpenAPI). Resumo:

- `GET /ppcs` devolve uma lista de `Versao`:
  - `unidade`, `curso`, `curso_nome`, `tipo_documento`, `origem` (`crawler` ou `upload`);
  - `formato`, `sha256`, `tamanho_bytes`, `paginas`, `precisa_ocr`, `titulo`;
  - `pagina_url`, `arquivo_url` (nulo no upload), `coletado_em`;
  - `links.arquivo` e `links.texto`, os caminhos de download.
- `GET /avisos` devolve a lista de `Aviso`, no mesmo formato de `data/avisos.json`.
- `POST /auth/login` recebe `email` e `senha` e devolve `access_token` (JWT de 15 min),
  `expira_em_segundos` e `usuario`; o refresh vai em cookie. `POST /auth/refresh` devolve o mesmo
  (204 sem cookie) e `POST /auth/logout` encerra a sessão.
- `POST /ppcs` exige `Authorization: Bearer <access_token>` de um coordenador da unidade ou admin
  do polo e responde 201 com a `Versao` criada. Erros: 401 (sem login válido), 403 (perfil ou
  unidade), 404 (curso não cadastrado), 409 (versão já existe), 413 (tamanho), 415 (não é
  documento), 422 (parâmetro inválido) e 503 (login desligado).
