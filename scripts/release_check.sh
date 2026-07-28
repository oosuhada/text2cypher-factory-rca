#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv. Install backend/requirements.txt first." >&2
  exit 1
fi
if ! command -v pnpm >/dev/null 2>&1; then
  echo "pnpm is required for the web release check." >&2
  exit 1
fi

echo "[1/9] Python regression suite"
.venv/bin/python -m unittest discover -s tests -v

echo "[2/9] Backend API·traceability·secret contract"
.venv/bin/python scripts/release_gate.py --json

echo "[3/9] Enterprise UI quality·visual baseline"
.venv/bin/python scripts/ui_quality_gate.py

echo "[4/9] Cross-surface architecture·critical UX contract"
.venv/bin/python scripts/cross_surface_release_gate.py

echo "[5/9] Next.js lint and production build"
(
  cd web
  pnpm install --frozen-lockfile
  pnpm lint
  pnpm build
)

echo "[6/9] React browser journey regression"
(
  cd web
  pnpm test:e2e
)

echo "[7/9] Script syntax"
for script in scripts/*.sh infra/*.sh; do
  bash -n "$script"
done
.venv/bin/python -m py_compile scripts/e2e_smoke.py
.venv/bin/python -m py_compile scripts/release_gate.py
.venv/bin/python -m py_compile scripts/ui_quality_gate.py
.venv/bin/python -m py_compile scripts/cross_surface_release_gate.py

echo "[8/9] Container contract"
if command -v docker >/dev/null 2>&1; then
  docker compose \
    --env-file "${P3_ENV_FILE:-.env}" \
    -f infra/docker-compose.product.yml \
    config --quiet
else
  echo "Docker CLI not installed; compose validation deferred to CI."
fi

echo "[9/9] Release documentation"
for document in \
  docs/api-contract.md \
  docs/backend-lineage.md \
  docs/backend-troubleshooting.md \
  docs/module-ownership.md \
  docs/final-presentation-evidence-pack.md \
  docs/refactor-stage5-final-release-gate.md \
  docs/refactor-final-audit-and-phase3-readiness.md \
  release/backend-v1.yml; do
  test -s "$document"
done

echo "Release checks PASS"
