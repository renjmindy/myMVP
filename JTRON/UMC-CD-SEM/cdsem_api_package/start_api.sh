#!/usr/bin/env bash
# Start the CD-SEM Predict API (Linux / WSL).  Optional: PORT, HOST, CDSEM_IMAGE_DIR, CDSEM_DATA_DIR, TESSERACT_CMD
cd "$(dirname "$0")"
exec .venv/bin/python -m uvicorn cdsem_api:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
