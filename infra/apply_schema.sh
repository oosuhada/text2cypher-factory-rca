#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

NEO4J_URI="${NEO4J_URI:-neo4j://localhost:7687}"
NEO4J_DATABASE="${NEO4J_DATABASE:-neo4j}"
NEO4J_USERNAME="${NEO4J_USERNAME:-neo4j}"

if [[ -z "${NEO4J_PASSWORD:-}" ]] && command -v security >/dev/null 2>&1; then
  NEO4J_PASSWORD="$(
    security find-generic-password \
      -s "p3-cip-dmd-neo4j" \
      -a "$NEO4J_USERNAME" \
      -w 2>/dev/null || true
  )"
fi

if [[ -z "${NEO4J_PASSWORD:-}" ]]; then
  echo "Set NEO4J_PASSWORD or register it in macOS Keychain." >&2
  exit 1
fi

if ! command -v cypher-shell >/dev/null 2>&1; then
  echo "cypher-shell is not installed." >&2
  exit 1
fi

cypher-shell \
  -a "$NEO4J_URI" \
  -d "$NEO4J_DATABASE" \
  -u "$NEO4J_USERNAME" \
  -p "$NEO4J_PASSWORD" \
  -f "$PROJECT_DIR/infra/schema.cypher"

cypher-shell \
  -a "$NEO4J_URI" \
  -d "$NEO4J_DATABASE" \
  -u "$NEO4J_USERNAME" \
  -p "$NEO4J_PASSWORD" \
  "SHOW INDEXES YIELD name, state WHERE state <> 'ONLINE' RETURN name, state;"
