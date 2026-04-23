#!/usr/bin/env bash
set -eu

if [ "$(id -u)" -eq 0 ]; then
    echo "Refusing to run deployment as root. Use a dedicated non-root account."
    exit 1
fi

echo ">>> Stopping bot (if running in screen 'discord_alice')..."
screen -S discord_alice -X quit || true

echo ">>> Pulling latest changes from Git..."
git pull origin master

echo ">>> Installing/updating dependencies..."
source venv/bin/activate
pip install -r requirements.txt
deactivate

echo ">>> Starting bot in a new screen session 'discord_alice'..."
screen -dmS discord_alice bash -c 'source venv/bin/activate && python3 bot.py'

echo "Done. Use 'screen -r discord_alice' to inspect logs."
