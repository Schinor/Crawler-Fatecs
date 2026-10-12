# Inventário dos sites (tarefa C1)

Levantamento feito em 12/10/2026, com acesso manual e intervalo de 2 s entre as requisições.

## Resumo

| Unidade | Site | Plataforma | `robots.txt` | PPC publicado? |
| --- | --- | --- | --- | --- |
| Pompeia | `www.fatecpompeia.edu.br` | Google Sites | não existe (404), então não há restrição | Sim, em 2 de 3 cursos (iframe do Google Drive) |
| Marília | `fatecmarilia.cps.sp.gov.br` (o antigo `fatecmarilia.edu.br` redireciona para cá) | WordPress do CPS | `Allow: /` | Não: só matriz curricular e ementário em PDF |

## Pompeia (Google Sites)

| Curso | Página | Onde está o PPC |
| --- | --- | --- |
| CST em Sistemas Inteligentes | `/sistemas-inteligentes` | `<iframe src="drive.google.com/file/d/<id>/preview">`. O nome "PPC CST Sistemas Inteligentes - Fatec Pompeia..." aparece no HTML, mas **fora** do atributo `title` do iframe |
| CST em Big Data no Agronegócio | `/bigdata` | Iframe do Drive, como acima ("PPC CST em Big Data no Agronegócio.pdf") |
| CST em Mecanização em Agricultura de Precisão | `/map` | **Não encontrado**. Só há vídeos do YouTube |

Observações:

- **O HTML estático basta (resposta do spike C2).** O iframe do Drive já vem no HTML, então não
  precisamos de Playwright.
- **A heurística atual do `discover.py` não acha nenhum PPC aqui.** O iframe não tem `title`, e o
  nome do arquivo fica num elemento vizinho. A tarefa C4 (pontuação por contexto) precisa olhar o
  texto ao redor do iframe.
- **A home embrulha alguns links** em `https://www.google.com/url?q=<url-real>`. O adaptador
  `google_sites` precisa desembrulhar o parâmetro `q`.
- **O menu do site se repete em todas as páginas** e traz vários PDFs do Drive que não são PPC:
  calendário, horários de aula e prova, Deliberação 106, regulamento da biblioteca. Eles precisam
  ser descartados.
- `/secretaria/ementa` tem os ementários dos 3 cursos (links "DOWNLOAD" para o Drive).

## Marília (WordPress do CPS)

| Curso | Página | Documentos curriculares |
| --- | --- | --- |
| CST em Alimentos | `/tecnologia-em-alimentos/` | Grades A31, B31 e C31 (2006 até hoje) e o ementário de cada grade |
| CST em Gestão Empresarial (EaD) | `/gestao-empresarial/` | "Grade gestão empresarial" e "Ementa gestão empresarial" |
| CST em Gestão Comercial | `/gestao-comercial/` | Matrizes C75 e M75 e os ementários de cada uma |

Observações:

- **Nenhum documento se chama PPC ou projeto pedagógico.** O que existe são **matrizes (grades)
  curriculares e ementários**, partes do PPC. Ver a pendência em `decisoes.md`.
- **Os PDFs ficam num Azure Blob do CPS** (`bkpsitecpsnew.blob.core.windows.net`), um domínio
  diferente do site. Ele precisa entrar como exceção permitida, como o Google Drive.
- **As grades têm código e período de vigência no nome** (por exemplo, "Grade C31 – 2014-2 até
  atual"). É um ótimo sinal para o versionamento.
- **A página de cada curso também lista documentos que não são PPC:** horários de aula e uma
  deliberação do CEETEPS (regulamento disciplinar). Eles precisam ser descartados.

## Hosts dos arquivos e `robots.txt`

| Host | `robots.txt` | Efeito |
| --- | --- | --- |
| `drive.google.com` | Permite `/file/...`, **proíbe `/uc`** (download direto) | O crawler não baixa os PPCs de Pompeia: `erro_drive` "bloqueado pelo robots.txt" |
| `drive.usercontent.google.com` | `Disallow: /` | Idem (é para onde a página de confirmação leva) |
| `bkpsitecpsnew.blob.core.windows.net` | Responde 400 (sem `robots.txt`) | Livre, igual a um 404 (RFC 9309) |

## Primeira rodada real (12/10/2026)

`fatecorg-crawler run --todas`, 33 s:

| Unidade | Resultado |
| --- | --- |
| Pompeia | PPC encontrado em TSI e Big Data, mas **download bloqueado pelo robots.txt do Drive**; MAP sem PPC |
| Marília | 12 documentos: 6 matrizes (PDF), 3 ementários em PDF e 3 ementários em `.zip` (Alimentos) |

- 3 matrizes de 1 página vieram como imagem (`precisa_ocr = true`).
- A segunda rodada seguida registrou só `sem_mudanca`, sem duplicar nada.
