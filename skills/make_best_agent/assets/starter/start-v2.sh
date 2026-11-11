#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"
exec env DATABASE_URL='' .venv-v2/bin/python -m uvicorn v2.api:app --host 0.0.0.0 --port 8511
