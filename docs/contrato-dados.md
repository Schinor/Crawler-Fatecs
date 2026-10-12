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
