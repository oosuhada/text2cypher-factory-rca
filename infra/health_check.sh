#!/usr/bin/env bash
set -euo pipefail

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
  echo "Neo4j password is unavailable." >&2
  exit 1
fi

cypher-shell \
  -a "$NEO4J_URI" \
  -d "$NEO4J_DATABASE" \
  -u "$NEO4J_USERNAME" \
  -p "$NEO4J_PASSWORD" \
  "RETURN 1 AS ready;"

cypher-shell \
  -a "$NEO4J_URI" \
  -d "$NEO4J_DATABASE" \
  -u "$NEO4J_USERNAME" \
  -p "$NEO4J_PASSWORD" \
  "SHOW CONSTRAINTS YIELD name RETURN count(*) AS constraint_count;
   SHOW INDEXES YIELD name, state
   WHERE name IN [
     'part_type_index',
     'process_run_anomaly_index',
     'measurement_feature_qc_index'
   ]
   RETURN name, state ORDER BY name;"
