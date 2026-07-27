#!/usr/bin/env bash
# CVSniper - dependency installer for Linux and macOS
# Run this once after cloning:  bash setup/setup.sh
set -euo pipefail

cd "$(dirname "$0")/.."

echo
echo "==============================================="
echo "  CVSniper - setup"
echo "==============================================="
echo

# --- Python -----------------------------------------------------------------
# python3 first: on many distros bare `python` is still 2.x or simply missing.
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "  ERROR: Python 3 was not found."
  echo "  Debian/Ubuntu : sudo apt install python3 python3-pip python3-venv"
  echo "  macOS         : brew install python"
  exit 1
fi

PYVER="$($PY -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "  Python found: $PYVER"

if ! $PY -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  echo "  ERROR: Python 3.10 or newer is required (found $PYVER)."
  exit 1
fi

# --- Dependencies ------------------------------------------------------------
# A venv keeps this off the system Python. Recent Debian and Homebrew refuse
# a plain `pip install` outside one anyway (PEP 668).
echo
if [ ! -d ".venv" ]; then
  echo "  Creating the virtual environment in .venv ..."
  $PY -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "  Installing dependencies (this takes a couple of minutes)..."
echo
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements.txt

# --- Config files ------------------------------------------------------------
# Only the *.default.py templates are versioned. The real config files hold
# personal data and API keys, so they stay out of git and are created here.
echo
echo "  Preparing the config files..."
for f in personals questions search settings secrets; do
  if [ -f "config/$f.py" ]; then
    echo "    config/$f.py already exists, left untouched"
  elif [ -f "config/$f.default.py" ]; then
    cp "config/$f.default.py" "config/$f.py"
    echo "    created config/$f.py"
  fi
done

echo
echo "==============================================="
echo "  Done. Start the bot with:"
echo
echo "      source .venv/bin/activate"
echo "      python runAiBot.py"
echo
echo "  Everything is configured from the settings"
echo "  window, no need to edit files by hand."
echo "==============================================="
echo
