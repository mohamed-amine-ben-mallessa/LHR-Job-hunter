#!/usr/bin/env bash
# Installe l'app sur un VPS Ubuntu et active le timer systemd quotidien.
# Usage : sudo bash deploy/deploy.sh
set -euo pipefail

APP_DIR="/opt/offres-salle-24h"
SRC_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo ">> Dépendances système (python venv)"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip

echo ">> Copie de l'app vers $APP_DIR"
mkdir -p "$APP_DIR"
# rsync si dispo, sinon cp ; on ne copie pas le .git ni le venv local
if command -v rsync >/dev/null 2>&1; then
  rsync -a --exclude '.git' --exclude '.venv' --exclude '__pycache__' \
        "$SRC_DIR"/ "$APP_DIR"/
else
  cp -r "$SRC_DIR"/. "$APP_DIR"/
fi

echo ">> Environnement Python"
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

if [ ! -f "$APP_DIR/.env" ]; then
  echo ">> ATTENTION : pas de .env. Copie de .env.example -> .env (à compléter !)"
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  echo "   Édite $APP_DIR/.env pour y mettre TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID."
fi

echo ">> Installation des units systemd"
cp "$APP_DIR/deploy/systemd/offres-salle.service" /etc/systemd/system/
cp "$APP_DIR/deploy/systemd/offres-salle.timer"   /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now offres-salle.timer

echo ">> Fait. Vérifie avec :"
echo "   systemctl list-timers offres-salle.timer"
echo "   sudo systemctl start offres-salle.service   # test immédiat"
echo "   journalctl -u offres-salle.service -n 50     # logs"
