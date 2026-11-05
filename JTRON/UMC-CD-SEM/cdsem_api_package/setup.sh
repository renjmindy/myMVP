#!/usr/bin/env bash
# One-time setup (Linux / WSL): creates .venv and installs the Python packages.
set -e
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
if ! command -v tesseract >/dev/null 2>&1; then
    echo
    echo "WARNING: tesseract was not found. Install it first:  sudo apt-get install -y tesseract-ocr"
fi
echo
echo "Setup finished. Start the API with:  ./start_api.sh"
