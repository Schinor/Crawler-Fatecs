#!/usr/bin/env bash
# Configura o Garage local depois do `make infra-up`: layout de um nó, chave de acesso
# (a mesma do .env) e bucket. Pode rodar quantas vezes quiser.
set -euo pipefail
cd "$(dirname "$0")/.."

# Lê só as variáveis necessárias (o .env tem valores com espaços e parênteses)
env_var() { grep -m1 "^$1=" .env | cut -d= -f2-; }
S3_ACCESS_KEY=$(env_var S3_ACCESS_KEY)
S3_SECRET_KEY=$(env_var S3_SECRET_KEY)
S3_BUCKET=$(env_var S3_BUCKET)
S3_ENDPOINT=$(env_var S3_ENDPOINT)
garage() { docker compose --env-file .env -f infra/docker-compose.yml exec -T -e RUST_LOG=warn garage /garage "$@"; }

echo "Aguardando o Garage..."
for _ in $(seq 1 30); do garage status >/dev/null 2>&1 && break; sleep 1; done

if garage status | grep -q "NO ROLE ASSIGNED"; then
  no=$(garage node id -q | cut -d@ -f1)
  garage layout assign -z dev -c 1G "$no"
  garage layout apply --version 1
fi

garage key info "$S3_ACCESS_KEY" >/dev/null 2>&1 ||
  garage key import --yes -n fatecorg-dev "$S3_ACCESS_KEY" "$S3_SECRET_KEY" >/dev/null

garage bucket info "$S3_BUCKET" >/dev/null 2>&1 || garage bucket create "$S3_BUCKET" >/dev/null
garage bucket allow --read --write --owner "$S3_BUCKET" --key "$S3_ACCESS_KEY" >/dev/null

echo "Garage pronto: bucket '$S3_BUCKET' em $S3_ENDPOINT"
