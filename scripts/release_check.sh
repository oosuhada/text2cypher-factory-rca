#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -x ".venv/bin/python" ]]; then
  echo "Missing .venv. Install backend/requirements.txt first." >&2
  exit 1
fi
if command -v pnpm >/dev/null 2>&1; then
  PNPM=(pnpm)
elif command -v corepack >/dev/null 2>&1; then
  PNPM=(corepack pnpm)
else
  echo "pnpm or corepack is required for the web release check." >&2
  exit 1
fi

echo "[1/11] Python regression suite"
.venv/bin/python -m unittest discover -s tests -v

echo "[2/11] Backend API·traceability·secret contract"
.venv/bin/python scripts/release_gate.py --json

echo "[3/11] Enterprise UI quality·visual baseline"
.venv/bin/python scripts/ui_quality_gate.py

echo "[4/11] Cross-surface architecture·critical UX contract"
.venv/bin/python scripts/cross_surface_release_gate.py

echo "[5/11] Product-user release contract"
.venv/bin/python scripts/product_user_release_gate.py --json

echo "[6/11] Stage 3-2 project router evaluation"
.venv/bin/python scripts/project_router_gate.py --json

echo "[7/11] Next.js lint and production build"
(
  cd web
  "${PNPM[@]}" install --frozen-lockfile
  "${PNPM[@]}" lint
  RELEASE_BUILD=1 "${PNPM[@]}" build
)

echo "[8/11] React browser journey regression"
(
  cd web
  "${PNPM[@]}" test:e2e
)

echo "[9/11] Script syntax"
for script in scripts/*.sh infra/*.sh; do
  bash -n "$script"
done
.venv/bin/python -m py_compile scripts/e2e_smoke.py
.venv/bin/python -m py_compile scripts/release_gate.py
.venv/bin/python -m py_compile scripts/ui_quality_gate.py
.venv/bin/python -m py_compile scripts/cross_surface_release_gate.py
.venv/bin/python -m py_compile scripts/product_user_release_gate.py
.venv/bin/python -m py_compile scripts/project_router_gate.py
.venv/bin/python -m py_compile backend/app/agent/state.py
.venv/bin/python -m py_compile backend/app/agent/checkpoints.py
.venv/bin/python -m py_compile backend/app/agent/project_router.py

echo "[10/11] Container contract"
if command -v docker >/dev/null 2>&1; then
  docker compose \
    --env-file "${P3_ENV_FILE:-.env}" \
    -f infra/docker-compose.product.yml \
    config --quiet
else
  echo "Docker CLI not installed; compose validation deferred to CI."
fi

echo "[11/11] Release documentation"
for document in \
  docs/api-contract.md \
  docs/backend-lineage.md \
  docs/backend-troubleshooting.md \
  docs/module-ownership.md \
  docs/final-presentation-evidence-pack.md \
  docs/refactor-stage5-final-release-gate.md \
  docs/refactor-final-audit-and-phase3-readiness.md \
  docs/enterprise-stage2-9-5-product-release-gate.md \
  docs/enterprise-stage3-1-langgraph-state-checkpoint.md \
  docs/enterprise-stage3-2-project-router.md \
  evaluation/project_router.yml \
  evaluation/product_user_release_baseline.json \
  release/backend-v1.yml; do
  test -s "$document"
done

echo "Release checks PASS"
