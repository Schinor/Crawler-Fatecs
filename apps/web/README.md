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
| `/busca?q=` | Busca no conteúdo dos documentos (português, sem acento), com o termo destacado | `GET /busca` |
| `/unidades/:unidade/cursos/:curso/comparar?de=&para=` | Comparação entre duas versões do curso | `GET /ppcs/{u}/{c}/comparar` |
| `/documentos` | Todos os documentos, com filtro por título, unidade e tipo | `GET /ppcs` |
| `/entrar` | Login de coordenadores e administradores | `POST /auth/login` |
| `/enviar` | Upload manual; exige login e devolve à página depois dele | `POST /ppcs` |

- **Banner de avisos:** aparece no início e na página do curso. O link "enviar o arquivo" abre o
  formulário já preenchido (`/enviar?unidade=&curso=&tipo=`).
- **Versões:** uma unidade pode publicar vários documentos do mesmo tipo (Marília tem uma matriz
  por grade). O histórico agrupa por **documento**, ou seja, pelo mesmo link de origem; só há
  "versão atual" e "anterior" quando o mesmo link mudou de conteúdo.
- **Sessão:** o token de acesso fica só na memória (`core/auth.ts`), nunca em `localStorage`. O
  refresh é um cookie `HttpOnly` que o JS não lê; por ele a sessão volta ao recarregar a página.
  O interceptor renova o token vencido e repete a requisição. O cookie exige a mesma origem,
  então use sempre o proxy (`/api`), e HTTPS em produção. No Safari, `http://localhost` não
  aceita cookie `Secure`: use `API_COOKIE_SEGURO=false` só no desenvolvimento;
- **Perfis na tela:** o menu e a guarda de rota são conveniência; quem decide é a API.
- **Segurança (A-8):** tudo que vem da API é exibido por interpolação (`{{ }}`). Não use
  `innerHTML` nem `bypassSecurityTrust*`; há um teste que garante isso no banner.
- **Acessibilidade:** link "pular para o conteúdo", foco visível, rótulos em todos os campos,
  `role="alert"` nos erros, alvos de toque de 44 px e contraste AA no tema claro e no escuro.
- **Celular:** nenhuma tela passa de 375 px; no celular, a tabela de documentos vira lista.

- **Busca:** a consulta fica na URL (dá para compartilhar o link). Aceita `"frase exata"`,
  `-palavra` e `or`. Os trechos chegam como dados e o `<mark>` é montado no template.
- **Comparação:** pequenas mudanças aparecem palavra por palavra (`<ins>`/`<del>`); trechos
  reescritos aparecem inteiros, antes e depois. Trechos iguais longos ficam recolhidos. O
  histórico do curso tem "Comparar com a anterior" quando um documento tem mais de uma versão.

Limitação atual: a lista de documentos busca até 200 itens (o máximo da API) e filtra no
navegador.

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
├── core/         # sessão de login, interceptor e guarda de rota
├── shared/       # banner de avisos, rótulos e formatação
├── features/     # unidades, curso, documentos, busca, comparar, enviar, entrar (rotas lazy)
└── testes/       # dados de teste e configuração do TestBed
```
