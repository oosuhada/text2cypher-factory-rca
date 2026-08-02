#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_ROOT="$PROJECT_ROOT/web"
cd "$WEB_ROOT"

if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm이 없습니다. Node.js와 pnpm을 먼저 설치하세요." >&2
  exit 1
fi

if [[ ! -d "node_modules" ]]; then
  pnpm install --frozen-lockfile
fi

exec pnpm dev \
  --hostname "${P3_WEB_HOST:-127.0.0.1}" \
  --port "${P3_WEB_PORT:-3000}"
