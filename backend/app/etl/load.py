"""Load validated CiP-DMD payloads into a project-scoped graph."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from neo4j import Driver

from .transform import GraphPayload


PARTS_QUERY = """
UNWIND $rows AS row
MERGE (part:Part {project_id: $project_id, part_id: row.part_id})
SET part.part_type = row.part_type,
    part.reworked = row.reworked,
    part.source_file = row.source_file
FOREACH (_ IN CASE WHEN row.subtype = 'Cylinder' THEN [1] ELSE [] END |
  SET part:Cylinder
)
FOREACH (_ IN CASE WHEN row.subtype = 'CylinderBottom' THEN [1] ELSE [] END |
  SET part:CylinderBottom
)
FOREACH (_ IN CASE WHEN row.subtype = 'PistonRod' THEN [1] ELSE [] END |
  SET part:PistonRod
)
"""

PROCESSES_QUERY = """
UNWIND $rows AS row
MERGE (process:Process {project_id: $project_id, name: row.name})
SET process.display_name = row.display_name
"""

EQUIPMENT_QUERY = """
UNWIND $rows AS row
MERGE (equipment:Equipment {
  project_id: $project_id, equipment_id: row.equipment_id
})
SET equipment.name = row.name,
    equipment.equipment_type = row.equipment_type
"""

ANOMALY_CLASSES_QUERY = """
UNWIND $rows AS row
MERGE (anomaly:AnomalyClass {
  project_id: $project_id, code: row.code
})
SET anomaly.name = row.name,
    anomaly.description = row.description,
    anomaly.is_normal = row.is_normal
"""

RUNS_QUERY = """
UNWIND $rows AS row
MATCH (part:Part {project_id: $project_id, part_id: row.part_id})
MATCH (process:Process {
  project_id: $project_id, name: row.process_name
})
OPTIONAL MATCH (equipment:Equipment {
  project_id: $project_id, equipment_id: row.equipment_id
})
MATCH (anomaly:AnomalyClass {
  project_id: $project_id, code: row.anomaly_code
})
MERGE (run:ProcessRun {project_id: $project_id, run_id: row.run_id})
SET run.sequence = row.sequence,
    run.anomaly = row.anomaly,
    run.start_time = row.start_time,
    run.end_time = row.end_time,
    run.sensor_file_count = row.sensor_file_count
MERGE (part)-[underwent:UNDERWENT]->(run)
SET underwent.project_id = $project_id
MERGE (run)-[instance_of:INSTANCE_OF]->(process)
SET instance_of.project_id = $project_id
FOREACH (_ IN CASE WHEN equipment IS NULL THEN [] ELSE [1] END |
  MERGE (run)-[run_on:RUN_ON]->(equipment)
  SET run_on.project_id = $project_id
)
MERGE (run)-[classified_as:CLASSIFIED_AS]->(anomaly)
SET classified_as.project_id = $project_id
"""

MEASUREMENTS_QUERY = """
UNWIND $rows AS row
MATCH (part:Part {project_id: $project_id, part_id: row.part_id})
MATCH (process:Process {
  project_id: $project_id, name: row.process_name
})
MERGE (measurement:QualityMeasurement {
  project_id: $project_id,
  measurement_id: row.measurement_id
})
SET measurement.feature = row.feature,
    measurement.value_text = row.value_text,
    measurement.value_numeric = row.value_numeric,
    measurement.qc_pass = row.qc_pass
FOREACH (_ IN CASE WHEN row.qc_pass = false THEN [1] ELSE [] END |
  SET measurement:QualityFailure
)
FOREACH (_ IN CASE WHEN row.qc_pass = true THEN [1] ELSE [] END |
  REMOVE measurement:QualityFailure
)
MERGE (part)-[has_measurement:HAS_MEASUREMENT]->(measurement)
SET has_measurement.project_id = $project_id
MERGE (measurement)-[for_process:FOR_PROCESS]->(process)
SET for_process.project_id = $project_id
"""

ASSEMBLIES_QUERY = """
UNWIND $rows AS row
MATCH (cylinder:Part:Cylinder {
  project_id: $project_id, part_id: row.cylinder_id
})
MATCH (component:Part {
  project_id: $project_id, part_id: row.component_id
})
MERGE (cylinder)-[relationship:ASSEMBLED_FROM]->(component)
SET relationship.component_role = row.component_role,
    relationship.project_id = $project_id
"""


def batches(
    rows: list[dict[str, Any]], size: int
) -> Iterable[list[dict[str, Any]]]:
    for start in range(0, len(rows), size):
        yield rows[start : start + size]


def apply_schema(driver: Driver, database: str, schema_path: Path) -> None:
    statements = [
        statement.strip()
        for statement in schema_path.read_text(encoding="utf-8").split(";")
        if statement.strip()
    ]
    for statement in statements:
        driver.execute_query(statement, database_=database, routing_="w")


def run_batches(
    driver: Driver,
    database: str,
    query: str,
    rows: list[dict[str, Any]],
    batch_size: int,
    project_id: str,
) -> dict[str, int]:
    totals = {
        "nodes_created": 0,
        "relationships_created": 0,
        "properties_set": 0,
        "labels_added": 0,
    }
    for batch in batches(rows, batch_size):
        result = driver.execute_query(
            query,
            rows=batch,
            project_id=project_id,
            database_=database,
            routing_="w",
        )
        counters = result.summary.counters
        for name in totals:
            totals[name] += getattr(counters, name)
    return totals


def load_payload(
    driver: Driver,
    database: str,
    payload: GraphPayload,
    schema_path: Path,
    batch_size: int = 500,
    project_id: str = "cip-dmd",
) -> dict[str, dict[str, int]]:
    apply_schema(driver, database, schema_path)
    return {
        "parts": run_batches(
            driver, database, PARTS_QUERY, payload.parts, batch_size, project_id
        ),
        "processes": run_batches(
            driver,
            database,
            PROCESSES_QUERY,
            payload.processes,
            batch_size,
            project_id,
        ),
        "equipment": run_batches(
            driver,
            database,
            EQUIPMENT_QUERY,
            payload.equipment,
            batch_size,
            project_id,
        ),
        "anomaly_classes": run_batches(
            driver,
            database,
            ANOMALY_CLASSES_QUERY,
            payload.anomaly_classes,
            batch_size,
            project_id,
        ),
        "process_runs": run_batches(
            driver,
            database,
            RUNS_QUERY,
            payload.process_runs,
            batch_size,
            project_id,
        ),
        "measurements": run_batches(
            driver,
            database,
            MEASUREMENTS_QUERY,
            payload.measurements,
            batch_size,
            project_id,
        ),
        "assemblies": run_batches(
            driver,
            database,
            ASSEMBLIES_QUERY,
            payload.assemblies,
            batch_size,
            project_id,
        ),
    }


def graph_counts(
    driver: Driver,
    database: str,
    project_id: str = "cip-dmd",
) -> dict[str, int]:
    scope = " WHERE n.project_id = $project_id RETURN count(n) AS count"
    node_queries = {
        "Part": "MATCH (n:Part)" + scope,
        "Process": "MATCH (n:Process)" + scope,
        "Equipment": "MATCH (n:Equipment)" + scope,
        "AnomalyClass": "MATCH (n:AnomalyClass)" + scope,
        "ProcessRun": "MATCH (n:ProcessRun)" + scope,
        "QualityMeasurement": "MATCH (n:QualityMeasurement)" + scope,
        "QualityFailure": (
            "MATCH (n:QualityMeasurement:QualityFailure)" + scope
        ),
    }
    counts = {
        name: int(
            driver.execute_query(
                query,
                project_id=project_id,
                database_=database,
                routing_="r",
            ).records[0]["count"]
        )
        for name, query in node_queries.items()
    }
    relationship_query = """
    MATCH ()-[relationship]->()
    WHERE type(relationship) = $relationship_type
      AND relationship.project_id = $project_id
    RETURN count(relationship) AS count
    """
    for relationship_type in (
        "ASSEMBLED_FROM",
        "UNDERWENT",
        "INSTANCE_OF",
        "RUN_ON",
        "CLASSIFIED_AS",
        "HAS_MEASUREMENT",
        "FOR_PROCESS",
    ):
        result = driver.execute_query(
            relationship_query,
            relationship_type=relationship_type,
            project_id=project_id,
            database_=database,
            routing_="r",
        )
        counts[relationship_type] = int(result.records[0]["count"])
    return counts
