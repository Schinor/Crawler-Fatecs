Front-end Angular. Gerar a partir da raiz do repositório (passo 4 de 01_MONOREPO_E_GITHUB.md).
Requer Node 24 LTS (o Angular CLI atual exige Node >= 22.22.3 ou >= 24.15).

    rm apps/web/README.md
    npx @angular/cli@latest new web --directory apps/web --routing --style=scss --ssr=false --skip-git
    cd apps/web && npm install   # gera o package-lock.json que o CI usa
