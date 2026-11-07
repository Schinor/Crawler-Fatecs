#!/usr/bin/env bash
# Agenda a coleta semanal (C9) nesta máquina: domingo às 03h, como decidido em docs/decisoes.md.
#
#   bash scripts/agendar.sh mostrar    # mostra o que seria instalado, sem mudar nada
#   bash scripts/agendar.sh instalar   # timer do systemd do usuário (ou cron, sem systemd)
#   bash scripts/agendar.sh status     # próxima execução e último log
#   bash scripts/agendar.sh remover
#
# Com o systemd, o timer é `Persistent=true`: se a máquina estiver desligada no horário, a coleta
# roda assim que ela ligar. O cron não faz isso. Para forçar o cron: FATECORG_AGENDADOR=cron.
#
# Variáveis opcionais: FATECORG_QUANDO (OnCalendar do systemd, padrão "Sun *-*-* 03:00:00"),
# FATECORG_CRON (padrão "0 3 * * 0"), FATECORG_SYSTEMD_DIR (padrão ~/.config/systemd/user).
set -euo pipefail

RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
NOME="fatecorg-coleta"
QUANDO="${FATECORG_QUANDO:-Sun *-*-* 03:00:00}"
CRON="${FATECORG_CRON:-0 3 * * 0}"
UNIDADES="${FATECORG_SYSTEMD_DIR:-$HOME/.config/systemd/user}"
MARCA="# $NOME"
UV="${FATECORG_UV:-$(command -v uv || echo "$HOME/.local/bin/uv")}"

agendador() {
  if [ -n "${FATECORG_AGENDADOR:-}" ]; then
    echo "$FATECORG_AGENDADOR"
  elif systemctl --user show-environment >/dev/null 2>&1; then
    echo systemd
  else
    echo cron
  fi
}

servico() {
  cat <<EOF
[Unit]
Description=FatecOrg: coleta semanal dos documentos curriculares
Documentation=file://$RAIZ/apps/crawler/README.md

[Service]
Type=oneshot
WorkingDirectory=$RAIZ
Environment="FATECORG_UV=$UV"
ExecStart=/usr/bin/env bash "$RAIZ/scripts/coleta-semanal.sh"
Nice=10
EOF
}

timer() {
  cat <<EOF
[Unit]
Description=FatecOrg: coleta semanal (timer)

[Timer]
OnCalendar=$QUANDO
Persistent=true
RandomizedDelaySec=10min

[Install]
WantedBy=timers.target
EOF
}

linha_cron() {
  echo "$CRON cd \"$RAIZ\" && FATECORG_UV=\"$UV\" bash scripts/coleta-semanal.sh >/dev/null 2>&1 $MARCA"
}

cron_sem_a_nossa() { crontab -l 2>/dev/null | grep -vF "$MARCA" || true; }

instalar() {
  [ -x "$UV" ] || { echo "uv não encontrado ($UV). Instale ou defina FATECORG_UV." >&2; exit 1; }
  if [ "$(agendador)" = systemd ]; then
    mkdir -p "$UNIDADES"
    servico >"$UNIDADES/$NOME.service"
    timer >"$UNIDADES/$NOME.timer"
    systemctl --user daemon-reload
    systemctl --user enable --now "$NOME.timer"
    echo "Timer instalado em $UNIDADES."
    if [ "$(loginctl show-user "$USER" -p Linger --value 2>/dev/null)" != yes ]; then
      echo "Atenção: o timer só roda com você logado. Para rodar sem sessão aberta:"
      echo "  loginctl enable-linger $USER"
    fi
  else
    { cron_sem_a_nossa; linha_cron; } | crontab -
    echo "Linha instalada no crontab."
  fi
  status
}

remover() {
  if [ -f "$UNIDADES/$NOME.timer" ]; then
    systemctl --user disable --now "$NOME.timer" || true
    rm -f "$UNIDADES/$NOME.timer" "$UNIDADES/$NOME.service"
    systemctl --user daemon-reload || true
    echo "Timer removido."
  fi
  if crontab -l 2>/dev/null | grep -qF "$MARCA"; then
    cron_sem_a_nossa | crontab -
    echo "Linha removida do crontab."
  fi
}

status() {
  if [ -f "$UNIDADES/$NOME.timer" ]; then
    systemctl --user list-timers "$NOME.timer" --no-pager || true
  elif crontab -l 2>/dev/null | grep -F "$MARCA"; then
    :
  else
    echo "Coleta semanal não agendada nesta máquina."
  fi
  ultimo=$(find "$RAIZ/data/logs" -maxdepth 1 -name 'coleta-*.log' -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | head -n1 | cut -d' ' -f2- || true)
  if [ -n "$ultimo" ]; then
    echo "Último log: $ultimo"
    tail -n 1 "$ultimo"
  fi
}

mostrar() {
  if [ "$(agendador)" = systemd ]; then
    echo "# $UNIDADES/$NOME.service"
    servico
    echo
    echo "# $UNIDADES/$NOME.timer"
    timer
  else
    echo "# linha do crontab"
    linha_cron
  fi
}

case "${1:-}" in
  mostrar | instalar | remover | status) "$1" ;;
  *)
    echo "uso: bash scripts/agendar.sh {mostrar|instalar|status|remover}" >&2
    exit 64
    ;;
esac
