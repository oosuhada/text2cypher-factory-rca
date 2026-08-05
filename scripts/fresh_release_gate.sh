#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop or Docker Engine is required." >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "Docker Compose v2 is required." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required for the black-box HTTP smoke test." >&2
  exit 1
fi

TEMP_ENV=""
ENV_FILE="${P3_RELEASE_ENV_FILE:-}"
if [[ -z "$ENV_FILE" ]]; then
  TEMP_ENV="$(mktemp "${TMPDIR:-/tmp}/factorygraph-release.XXXXXX")"
  ENV_FILE="$TEMP_ENV"
  RELEASE_PASSWORD="release-$(date +%s)-$$"
  printf '%s\n' \
    "NEO4J_PASSWORD=$RELEASE_PASSWORD" \
    "P3_API_PROVIDER=gold" \
    > "$ENV_FILE"
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Release environment file not found: $ENV_FILE" >&2
  exit 1
fi

COMPOSE=(
  docker compose
  --env-file "$ENV_FILE"
  -f infra/docker-compose.product.yml
)

cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if [[ $exit_code -ne 0 ]]; then
    "${COMPOSE[@]}" logs --no-color --tail 200 || true
  fi
  "${COMPOSE[@]}" down --volumes --remove-orphans || true
  if [[ -n "$TEMP_ENV" ]]; then
    rm -f "$TEMP_ENV"
  fi
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

echo "[fresh-release] Compose contract"
"${COMPOSE[@]}" config --quiet

echo "[fresh-release] Build and start clean stack"
"${COMPOSE[@]}" up --build --wait

echo "[fresh-release] Black-box HTTP E2E"
python3 scripts/e2e_smoke.py --timeout "${P3_E2E_TIMEOUT:-120}"

echo "Fresh environment release gate PASS"
