#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

API_PID=""
WEB_PID=""

cleanup() {
  [[ -z "$WEB_PID" ]] || kill "$WEB_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

API_LIVE_URL="http://${P3_API_HOST:-127.0.0.1}:${P3_API_PORT:-8000}/api/v1/health/live"

if curl --silent --fail "$API_LIVE_URL" >/dev/null 2>&1; then
  echo "기존 FastAPI 인스턴스를 사용합니다."
else
  ./scripts/run_api.sh &
  API_PID=$!

  for _ in {1..30}; do
    if curl --silent --fail "$API_LIVE_URL" >/dev/null; then
      break
    fi
    sleep 0.3
  done

  if ! curl --silent --fail "$API_LIVE_URL" >/dev/null; then
    echo "FastAPI가 제한 시간 안에 시작되지 않았습니다." >&2
    exit 1
  fi
fi

./scripts/run_web.sh &
WEB_PID=$!

echo "FactoryGraph RCA"
echo "- Product UI: http://${P3_WEB_HOST:-127.0.0.1}:${P3_WEB_PORT:-3000}"
echo "- API docs:   http://${P3_API_HOST:-127.0.0.1}:${P3_API_PORT:-8000}/docs"

wait "$WEB_PID"
