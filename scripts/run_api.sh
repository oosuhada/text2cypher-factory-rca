#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/uvicorn" ]]; then
  echo "Python 환경이 없습니다. 먼저 다음 명령을 실행하세요:"
  echo "python3 -m venv .venv"
  echo ".venv/bin/pip install -r backend/requirements.txt"
  exit 1
fi

exec .venv/bin/uvicorn backend.app.api.main:app \
  --host "${P3_API_HOST:-127.0.0.1}" \
  --port "${P3_API_PORT:-8000}"
