#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Python virtual environment is missing: $PROJECT_ROOT/.venv" >&2
  exit 1
fi

if ! ./infra/health_check.sh >/dev/null 2>&1; then
  echo "Neo4j is not ready; restarting it in reader mode."
  ./infra/set_homebrew_mode.sh reader
fi

echo "Running demo preflight..."
.venv/bin/python scripts/demo_preflight.py

echo "Verifying four fixed Gold demo scenarios..."
.venv/bin/python scripts/demo_smoke.py

echo "Starting Factory Graph RCA..."
exec ./scripts/run_streamlit.sh "$@"
