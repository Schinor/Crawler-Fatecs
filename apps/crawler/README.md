# fatecorg-crawler

Coleta os documentos curriculares (PPC, matriz curricular e ementário) publicados nos sites das
Fatecs, guarda cada versão por SHA-256 e extrai o texto dos PDFs. Na Fase 1 a saída fica só em
`data/`, sem banco.

## Comandos

```bash
uv run fatecorg-crawler unidades                  # unidades e cursos do seed
uv run fatecorg-crawler inventario --unidade X    # mostra o que acharia, sem baixar
uv run fatecorg-crawler run --unidade pompeia     # coleta uma unidade
uv run fatecorg-crawler run --todas               # todas as unidades ativas
uv run fatecorg-crawler reprocessar --data 2026-10-12   # parser sobre o HTML salvo, sem rede
uv run fatecorg-crawler relatorio                 # cobertura por curso, a partir de coletas.jsonl
```

## Como funciona

```text
seeds/unidades.yaml → sources/ (páginas de curso) → fetch.py (robots, 2 s por host, cache)
  → discover.py (pontua links e iframes) → download.py (formato, SHA-256)
  → sink.py (dedup por SHA) → data/ppcs/... + extract.py (texto) → data/ppcs.jsonl
```

| Módulo | Responsabilidade |
| --- | --- |
| `config.py` | Configuração (`CRAWLER_*` no `.env`) |
| `fetch.py` | HTTP educado: `robots.txt`, rate limit por host, 3 tentativas com backoff (rede, 429, 5xx), `ETag`/`Last-Modified`, HTML bruto + `.meta.json` salvos |
| `sources/` | Adaptadores: `google_sites` (Pompeia) e `generico` (WordPress do CPS e demais) |
| `discover.py` | Pontuação: termos de PPC, matriz e ementário somam; deliberação, horário, calendário etc. subtraem |
| `download.py` | Drive (com página de confirmação), assinatura do arquivo (`pdf`, `doc`, `docx`, `odt`, `zip`) |
| `extract.py` | Texto com PyMuPDF, normalizado; `precisa_ocr` se tiver menos de 500 caracteres |
| `sink.py` | `JsonlSink` (Fase 1). A Fase 2 troca por `RepoSink` com a mesma interface |
| `pipeline.py` | Orquestra tudo e registra uma `Coleta` por resultado |

Status de cada coleta: `novo_ppc`, `sem_mudanca`, `sem_ppc`, `erro_http`, `erro_drive`, `nao_pdf`.

## Como adicionar uma unidade

1. Rode o inventário manual: abra o site e anote onde ficam as páginas de curso e os documentos.
2. Acrescente em `seeds/unidades.yaml`:
   ```yaml
   - slug: garca
     nome: Fatec Garça
     cidade: Garça
     site_url: https://...
     plataforma: wordpress        # google_sites | wordpress | generico
     cursos:
       - slug: nome-do-curso
         nome: CST em ...
         url: https://.../pagina-do-curso/
   ```
   Sem `cursos`, o adaptador tenta descobrir as páginas sozinho (menu ou BFS de até 2 níveis).
3. `uv run fatecorg-crawler inventario --unidade garca`: confira se os documentos certos aparecem.
4. Se os arquivos ficam em outro domínio, inclua-o em `dominios_arquivos` (`config.py`).
5. Salve o HTML de uma página em `tests/fixtures/<unidade>_<curso>.html` **sem `<script>`**
   (o gitleaks bloqueia chaves embutidas nos scripts) e escreva um teste de snapshot.
6. Registre a unidade em `docs/inventario-sites.md`.

## Como criar um adaptador

Só se o inventário mostrar que o `generico` não serve. Crie `sources/<plataforma>.py` com uma
classe que tenha `plataforma` e `paginas_de_curso(unidade, fetcher) -> list[PaginaCurso]`, e
registre-a em `sources/__init__.py`. Documente no próprio arquivo qual exceção do site ele trata.

## Testes

```bash
uv run pytest apps/crawler          # unitários, snapshots e HTTP simulado (rodam no CI)
uv run pytest -m rede               # acessa os sites de verdade (só local)
```

## Regras de etiqueta

O crawler respeita o `robots.txt` e **nunca o contorna**, espera 2 s entre requisições ao mesmo
host, identifica-se no User-Agent e roda uma vez por semana, de madrugada.
