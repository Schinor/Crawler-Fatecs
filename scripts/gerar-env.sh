#!/usr/bin/env bash
# Cria o .env local a partir do .env.example, gerando segredos aleatórios.
# Nunca sobrescreve um .env existente. O .env não é versionado.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -e .env ]; then
  echo ".env já existe; nada a fazer. Apague-o se quiser gerar de novo." >&2
  exit 0
fi

hex() { openssl rand -hex "$1"; }

sed \
  -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(hex 16)|" \
  -e "s|^GARAGE_RPC_SECRET=.*|GARAGE_RPC_SECRET=$(hex 32)|" \
  -e "s|^GARAGE_ADMIN_TOKEN=.*|GARAGE_ADMIN_TOKEN=$(hex 32)|" \
  -e "s|^S3_ACCESS_KEY=.*|S3_ACCESS_KEY=GK$(hex 12)|" \
  -e "s|^S3_SECRET_KEY=.*|S3_SECRET_KEY=$(hex 32)|" \
  .env.example > .env
chmod 600 .env

# DATABASE_URL usa a senha gerada
senha=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)
sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+psycopg://fatecorg:${senha}@localhost:5432/fatecorg|" .env

echo ".env criado com segredos aleatórios (permissão 600)."
