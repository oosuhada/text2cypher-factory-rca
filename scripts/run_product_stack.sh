#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE="${P3_ENV_FILE:-.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.example and set NEO4J_PASSWORD." >&2
  exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker Desktop or Docker Engine is required." >&2
  exit 1
fi

docker compose \
  --env-file "$ENV_FILE" \
  -f infra/docker-compose.product.yml \
  up --build --wait

python3 scripts/e2e_smoke.py

echo "FactoryGraph RCA stack is ready:"
echo "- Next.js:  http://127.0.0.1:3000"
echo "- FastAPI:  http://127.0.0.1:8000/docs"
echo "- Streamlit: http://127.0.0.1:8501"
echo "- Neo4j:    http://127.0.0.1:7474"
