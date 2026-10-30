#!/usr/bin/env bash
# CVSniper - start the bot on Linux / macOS:  bash start.sh
# Runs setup/setup.sh the first time (or whenever the venv is missing), then
# starts the bot inside the venv, so nobody has to remember to activate it.
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ] || ! .venv/bin/python -c "import selenium, flask, pyautogui, undetected_chromedriver" >/dev/null 2>&1; then
  echo "  First run: installing dependencies..."
  bash setup/setup.sh
fi

exec .venv/bin/python runAiBot.py "$@"
