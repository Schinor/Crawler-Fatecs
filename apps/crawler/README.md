# fatecorg-crawler

Coleta os documentos curriculares (PPC, matriz curricular e ementário) publicados nos sites das
Fatecs, guarda cada versão por SHA-256 e extrai o texto dos PDFs. A saída vai para `data/`
(`--sink jsonl`, padrão) ou para o Postgres + Garage (`--sink banco`, Fase 2).

## Comandos

```bash
uv run fatecorg-crawler unidades                  # unidades e cursos do seed
uv run fatecorg-crawler inventario --unidade X    # mostra o que acharia, sem baixar
uv run fatecorg-crawler run --unidade pompeia     # coleta uma unidade
uv run fatecorg-crawler run --todas               # todas as unidades ativas
uv run fatecorg-crawler run --todas --sink banco  # grava no Postgres + Garage (Fase 2)
uv run fatecorg-crawler importar                  # copia data/ para o banco e o Garage
uv run fatecorg-crawler indexar                   # texto das versões antigas para a busca (migration 0002)
uv run fatecorg-crawler reprocessar --data 2026-10-12   # parser sobre o HTML salvo, sem rede
uv run fatecorg-crawler relatorio                 # cobertura por curso, a partir de coletas.jsonl
uv run fatecorg-crawler avisos                    # documentos que precisam de ação humana
uv run fatecorg-crawler notificar-falha --log X --codigo N   # usado pela coleta agendada
```

O `run` sai com código 2 quando nenhuma página foi lida (sem rede ou sites fora do ar).

## Como funciona

```text
seeds/unidades.yaml → sources/ (páginas de curso) → fetch.py (robots, 2 s por host, cache)
  → discover.py (pontua links e iframes) → download.py (formato, SHA-256)
  → sink.py (dedup por SHA) → arquivo + extract.py (texto) → data/ ou Postgres + Garage
```

| Módulo | Responsabilidade |
| --- | --- |
| `config.py` | Configuração (`CRAWLER_*` no `.env`) |
| `fetch.py` | HTTP educado: `robots.txt`, rate limit por host, 3 tentativas com backoff (rede, 429, 5xx), `ETag`/`Last-Modified`, HTML bruto + `.meta.json` salvos |
| `sources/` | Adaptadores: `google_sites` (Pompeia) e `generico` (WordPress do CPS e demais) |
| `discover.py` | Pontuação: termos de PPC, matriz e ementário somam; deliberação, horário, calendário etc. subtraem |
| `download.py` | Drive (com página de confirmação), assinatura do arquivo (`pdf`, `doc`, `docx`, `odt`, `zip`) |
| `extract.py` | Texto com PyMuPDF, normalizado; `precisa_ocr` se tiver menos de 500 caracteres |
| `sink.py` | `JsonlSink` (`data/`) e `RepoSink` (Postgres + Garage), com a mesma interface: versões, coletas, arquivos e avisos |
| `importar.py` | Copia a saída da Fase 1 para o banco; pode rodar de novo sem duplicar |
| `pipeline.py` | Orquestra tudo e registra uma `Coleta` por resultado |
| `agendamento.py` | Coleta agendada: detecta rodada sem nenhuma página lida e monta o e-mail de falha com os segredos trocados por `***` |
| `avisos.py` | Avisos abertos (`data/avisos.json`), ex.: PPC no Drive bloqueado pelo `robots.txt`; e-mail ao responsável quando um aviso aparece |

Status de cada coleta: `novo_ppc`, `sem_mudanca`, `sem_ppc`, `erro_http`, `erro_drive`, `nao_pdf`.

## Coleta agendada (C9)

A coleta roda uma vez por semana, domingo às 03h (`docs/decisoes.md`), na máquina de quem
agendar:

```bash
make agendar          # instala o timer do systemd do usuário (ou uma linha no cron)
make agendamento      # próxima execução e último log
make coleta-semanal   # roda a rodada agendada agora, à mão
make desagendar       # remove o agendamento
bash scripts/agendar.sh mostrar   # mostra o que seria instalado, sem mudar nada
```

- `scripts/coleta-semanal.sh` roda `fatecorg-crawler run --todas` com o sink do `.env`
  (`CRAWLER_SINK`) e grava o log em `data/logs/coleta-<data>.log`. Ele guarda os 12 logs mais
  recentes, ou três meses de rodadas;
- só uma rodada por vez (`flock`): se a anterior ainda estiver rodando, a nova sai sem fazer nada;
- se a rodada falhar (código diferente de 0), o fim do log vai por e-mail ao responsável
  (`NOTIFICACAO_*` no `.env`), com senhas, tokens e chaves trocados por `***`;
- com o **systemd**, o timer é `Persistent=true`: se a máquina estiver desligada no domingo, a
  coleta roda quando ela ligar. Para rodar sem sessão aberta: `loginctl enable-linger $USER`;
- no **WSL**, a coleta só roda com o WSL ligado. Nesse caso o `Persistent=true` faz a rodada
  atrasada acontecer na próxima vez que ele abrir;
- sem systemd, o script usa o cron, que **não** recupera rodadas perdidas.

O GitHub Actions não serve para isso: ele não guarda `data/` entre as execuções e não alcança o
banco local.

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
