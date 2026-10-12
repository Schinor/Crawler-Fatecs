# ADR 0001: Monorepo com uv workspace

Status: aceito

## Contexto
Crawler e API gravam as mesmas entidades (Unidade, Curso, VersãoPPC). Em repositórios
separados o contrato de dados viraria um acordo verbal.

## Decisão
Um repositório. Python em uv workspace (`packages/core`, `apps/crawler`, `apps/api`);
Angular em `apps/web` com npm próprio.

## Consequências
Um único `uv.lock`; mudança no domínio quebra o CI de quem depende dele no mesmo PR.
