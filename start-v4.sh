#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"
# Local default matches the existing V2 launcher. Opt in to configured PostgreSQL.
if [[ "${KGT_USE_POSTGRES:-0}" != "1" ]]; then
  export DATABASE_URL='' POSTGRES_URL=''
fi
exec .venv-v2/bin/python -m uvicorn v2.api:app --host 127.0.0.1 --port "${KGT_PORT:-8514}"
