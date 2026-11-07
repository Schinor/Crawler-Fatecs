#!/usr/bin/env bash
# Rodada agendada do crawler (C9): coleta todas as unidades e guarda o log em data/logs/.
# Quem chama é o timer do systemd ou o cron instalado por scripts/agendar.sh. Também pode ser
# rodado à mão: bash scripts/coleta-semanal.sh
#
# - Uma rodada por vez (flock): se a anterior ainda estiver rodando, esta sai sem fazer nada.
# - O sink vem do .env (CRAWLER_SINK=jsonl ou banco).
# - Se a rodada falhar, `fatecorg-crawler notificar-falha` manda o fim do log por e-mail
#   (com os segredos trocados por ***), quando o SMTP está configurado no .env.
#
# Variáveis opcionais: FATECORG_UV (caminho do uv), FATECORG_LOG_DIR (padrão data/logs) e
# FATECORG_LOGS_MANTER (quantos logs guardar, padrão 12: três meses de rodadas semanais).
set -euo pipefail
cd "$(dirname "$0")/.."

UV="${FATECORG_UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"
LOG_DIR="${FATECORG_LOG_DIR:-data/logs}"
MANTER="${FATECORG_LOGS_MANTER:-12}"

umask 077  # o log tem URLs e caminhos locais: só o dono lê
mkdir -p "$LOG_DIR"

exec 9>"$LOG_DIR/.coleta.lock"
if ! flock -n 9; then
  echo "Outra coleta ainda está rodando; esta foi ignorada." >&2
  exit 0
fi

LOG="$LOG_DIR/coleta-$(date +%Y-%m-%dT%H%M%S).log"
echo "== início $(date -Iseconds) em $(hostname)" >"$LOG"
codigo=0
"$UV" run --frozen fatecorg-crawler run --todas >>"$LOG" 2>&1 || codigo=$?
echo "== fim $(date -Iseconds), código $codigo" >>"$LOG"

# Rotação: mantém só os $MANTER logs mais recentes
find "$LOG_DIR" -maxdepth 1 -name 'coleta-*.log' -printf '%T@ %p\n' \
  | sort -rn | tail -n +"$((MANTER + 1))" | cut -d' ' -f2- | xargs -r rm -f --

if [ "$codigo" -ne 0 ]; then
  # A saída vai para uma variável: o comando lê o log, então não escreve nele ao mesmo tempo
  aviso=$("$UV" run --frozen fatecorg-crawler notificar-falha --log "$LOG" --codigo "$codigo" 2>&1) || true
  echo "$aviso" >>"$LOG"
fi
echo "Log: $LOG (código $codigo)"
exit "$codigo"
