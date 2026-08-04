#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
if [[ "$MODE" != "loader" && "$MODE" != "reader" ]]; then
  echo "Usage: $0 loader|reader" >&2
  exit 1
fi

NEO4J_CONF="${NEO4J_CONF:-/opt/homebrew/opt/neo4j/libexec/conf/neo4j.conf}"
NEO4J_ADMIN="${NEO4J_ADMIN:-/opt/homebrew/opt/neo4j/bin/neo4j-admin}"
NEO4J_BIN="${NEO4J_BIN:-/opt/homebrew/opt/neo4j/bin/neo4j}"

if [[ ! -f "$NEO4J_CONF" ]]; then
  echo "Neo4j configuration not found: $NEO4J_CONF" >&2
  exit 1
fi

perl -0pi -e \
  's/\n?# P3 local database access mode\nserver\.databases\.read_only=neo4j\n?//g' \
  "$NEO4J_CONF"

if [[ "$MODE" == "reader" ]]; then
  printf '\n# P3 local database access mode\nserver.databases.read_only=neo4j\n' \
    >> "$NEO4J_CONF"
fi

"$NEO4J_ADMIN" server validate-config
# `brew services restart` can leave launchd loaded without a running
# process after rapid mode changes. A complete bootout/bootstrap cycle is
# slower by a few seconds but deterministic for the loader→reader boundary.
brew services stop neo4j || true
for _ in {1..120}; do
  if ! "$NEO4J_BIN" status >/dev/null 2>&1; then
    break
  fi
  sleep 0.5
done
if "$NEO4J_BIN" status >/dev/null 2>&1; then
  echo "Neo4j did not stop within 60 seconds." >&2
  exit 1
fi
brew services start neo4j

if [[ "$MODE" == "reader" ]]; then
  echo "Neo4j restarted in database-level read-only mode."
else
  echo "Neo4j restarted in loader/read-write mode."
fi
