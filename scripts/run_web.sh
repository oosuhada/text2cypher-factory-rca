#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_ROOT="$PROJECT_ROOT/web"
cd "$WEB_ROOT"

if command -v pnpm >/dev/null 2>&1; then
  PNPM=(pnpm)
elif command -v corepack >/dev/null 2>&1; then
  PNPM=(corepack pnpm)
else
  echo "pnpm 또는 corepack이 없습니다. Node.js를 먼저 설치하세요." >&2
  exit 1
fi

if [[ ! -d "node_modules" ]]; then
  "${PNPM[@]}" install --frozen-lockfile
fi

exec "${PNPM[@]}" dev \
  --hostname "${P3_WEB_HOST:-127.0.0.1}" \
  --port "${P3_WEB_PORT:-3000}"
