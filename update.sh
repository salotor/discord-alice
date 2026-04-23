#!/usr/bin/env bash
set -eu

SYNC_DEPS=0
if [ "${1:-}" = "--sync-deps" ]; then
    SYNC_DEPS=1
elif [ $# -gt 0 ]; then
    echo "Unknown argument: $1"
    echo "Usage: ./update.sh [--sync-deps]"
    exit 1
fi

if [ "$(id -u)" -eq 0 ]; then
    echo "Refusing to run deployment as root. Use a dedicated non-root account."
    exit 1
fi

current_head="$(git rev-parse HEAD)"

echo ">>> Fetching latest changes from Git..."
git fetch origin master

requirements_changed=0
if ! git diff --quiet "$current_head" FETCH_HEAD -- requirements.txt; then
    requirements_changed=1
fi

if [ "$requirements_changed" -eq 1 ] && [ "$SYNC_DEPS" -ne 1 ]; then
    echo "requirements.txt changed in the incoming revision."
    echo "Re-run deployment with ./update.sh --sync-deps to apply the pinned dependency set."
    exit 1
fi

echo ">>> Stopping bot (if running in screen 'discord_alice')..."
screen -S discord_alice -X quit || true

echo ">>> Fast-forwarding code to origin/master..."
git merge --ff-only FETCH_HEAD

if [ "$SYNC_DEPS" -eq 1 ]; then
    echo ">>> Syncing pinned dependencies from requirements.txt..."
    source venv/bin/activate
    python -m pip install --requirement requirements.txt
    deactivate
else
    echo ">>> Skipping dependency sync. Run ./update.sh --sync-deps when requirements.txt changes."
fi

echo ">>> Starting bot in a new screen session 'discord_alice'..."
screen -dmS discord_alice bash -c 'source venv/bin/activate && python3 bot.py'

echo "Done. Use 'screen -r discord_alice' to inspect logs."
