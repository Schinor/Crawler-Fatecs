# fatecorg-web

Front-end Angular do FatecOrg: consulta dos documentos curriculares coletados pelo crawler e
upload manual. Angular 22 com componentes standalone, signals, `httpResource` e rotas lazy.

## Rodar

```bash
# na raiz: API com o banco e o Garage do .env
make infra-up && make migrate
uv run uvicorn fatecorg_api.main:app --reload     # http://localhost:8000

# aqui
npm install
npx ng serve                                      # http://localhost:4200
```

O `ng serve` repassa `/api/*` para `http://localhost:8000` (`proxy.conf.json`), então o
navegador fala com uma origem só e não há CORS. Em produção, o proxy reverso faz o mesmo:
serve o build (`dist/web/browser`) e repassa `/api/` para o uvicorn.

## Telas

| Rota | Tela | API |
| --- | --- | --- |
| `/` | Unidades e cursos, com o número de documentos, a última coleta e o selo "precisa de ação" | `GET /unidades`, `/ppcs`, `/avisos` |
| `/unidades/:unidade/cursos/:curso` | Histórico do curso: cada documento e suas versões (atual e anteriores), downloads e texto extraído | `GET /ppcs?unidade=&curso=`, `/avisos` |
| `/documentos` | Todos os documentos, com filtro por texto (sem acento), unidade e tipo | `GET /ppcs` |
| `/enviar` | Upload manual com o token (`API_TOKEN_UPLOAD`) | `POST /ppcs` |

- **Banner de avisos:** aparece no início e na página do curso. O link "enviar o arquivo" abre o
  formulário já preenchido (`/enviar?unidade=&curso=&tipo=`).
- **Versões:** uma unidade pode publicar vários documentos do mesmo tipo (Marília tem uma matriz
  por grade). O histórico agrupa por **documento**, ou seja, pelo mesmo link de origem; só há
  "versão atual" e "anterior" quando o mesmo link mudou de conteúdo.
- **Token do upload:** é digitado a cada envio e fica só na memória da tela. Nunca vai para
  `localStorage`.
- **Segurança (A-8):** tudo que vem da API é exibido por interpolação (`{{ }}`). Não use
  `innerHTML` nem `bypassSecurityTrust*`; há um teste que garante isso no banner.
- **Acessibilidade:** link "pular para o conteúdo", foco visível, rótulos em todos os campos,
  `role="alert"` nos erros, alvos de toque de 44 px e contraste AA no tema claro e no escuro.
- **Celular:** nenhuma tela passa de 375 px; no celular, a tabela de documentos vira lista.

Limitações atuais: a lista de documentos busca até 200 itens (o máximo da API) e filtra no
navegador; a busca no conteúdo dos PPCs (full-text, A3) e a comparação entre versões (W4)
dependem de rotas novas na API.

## Contrato com a API

Os tipos de `src/app/api/esquema.ts` são **gerados** do OpenAPI da API. Não edite à mão:

```bash
uv run python scripts/exportar-openapi.py    # na raiz: grava apps/web/openapi.json
npm run api:tipos                            # aqui: gera src/app/api/esquema.ts
```

O CI confere os dois passos. Se uma rota ou schema da API mudar sem regenerar, o build quebra.
Os apelidos usados nas telas (`Versao`, `Unidade`, `Aviso`...) ficam em `src/app/api/tipos.ts`.

O `openapi-typescript` roda pelo `npx` com versão fixa, porque ainda pede TypeScript 5 e o
Angular 22 usa o 6.

## Testes e formatação

```bash
npx ng test --watch=false        # Vitest + jsdom, com HttpTestingController
npx prettier --check "src/**/*.{ts,html,css}"
npx ng build
```

## Estrutura

```text
src/app/
├── api/          # Api (HttpClient), tipos gerados (esquema.ts) e apelidos (tipos.ts)
├── shared/       # banner de avisos, rótulos e formatação
├── features/     # unidades, curso, documentos, enviar (uma rota lazy cada)
└── testes/       # dados de teste e configuração do TestBed
```
