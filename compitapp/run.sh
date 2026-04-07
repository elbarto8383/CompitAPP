#!/usr/bin/env bash
set -e

CONFIG_PATH=/data/options.json

if [ ! -f "$CONFIG_PATH" ]; then
    echo "[run.sh] ERRORE: $CONFIG_PATH non trovato."
    exit 1
fi

echo "[run.sh] Lettura configurazione..."

export TELEGRAM_TOKEN=$(jq --raw-output '.telegram_token // ""' $CONFIG_PATH)
export TELEGRAM_CHAT_IDS=$(jq --raw-output '.telegram_chat_ids // ""' $CONFIG_PATH)
export SOGLIA_VOTO=$(jq --raw-output '.soglia_voto_alert // 7' $CONFIG_PATH)
export ORARIO_REMINDER=$(jq --raw-output '.orario_reminder_sera // "20:00"' $CONFIG_PATH)
export POLLING_MINUTI=$(jq --raw-output '.polling_intervallo_minuti // 30' $CONFIG_PATH)
export SUPERVISOR_TOKEN="${SUPERVISOR_TOKEN}"
export DB_PATH="/data/compitapp.db"

# Legge array studenti e lo passa come JSON
export STUDENTI=$(jq --raw-output '.studenti // []' $CONFIG_PATH | jq -c '.')

echo "[run.sh] Configurazione:"
echo "  TELEGRAM_TOKEN     = ${TELEGRAM_TOKEN:0:15}..."
echo "  TELEGRAM_CHAT_IDS  = $TELEGRAM_CHAT_IDS"
echo "  SOGLIA_VOTO        = $SOGLIA_VOTO"
echo "  ORARIO_REMINDER    = $ORARIO_REMINDER"
echo "  POLLING_MINUTI     = $POLLING_MINUTI"
echo "  STUDENTI           = $STUDENTI"

echo "[run.sh] Avvio CompitAPP sulla porta 5002..."
exec python3 /app/app.py
