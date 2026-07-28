// P3 CiP-DMD MVP schema for Neo4j 5.x
// Idempotent: safe to run more than once.

CREATE CONSTRAINT part_project_id_unique IF NOT EXISTS
FOR (part:Part)
REQUIRE (part.project_id, part.part_id) IS UNIQUE;

CREATE CONSTRAINT process_project_name_unique IF NOT EXISTS
FOR (process:Process)
REQUIRE (process.project_id, process.name) IS UNIQUE;

CREATE CONSTRAINT process_run_project_id_unique IF NOT EXISTS
FOR (run:ProcessRun)
REQUIRE (run.project_id, run.run_id) IS UNIQUE;

CREATE CONSTRAINT measurement_project_id_unique IF NOT EXISTS
FOR (measurement:QualityMeasurement)
REQUIRE (measurement.project_id, measurement.measurement_id) IS UNIQUE;

CREATE CONSTRAINT equipment_project_id_unique IF NOT EXISTS
FOR (equipment:Equipment)
REQUIRE (equipment.project_id, equipment.equipment_id) IS UNIQUE;

CREATE CONSTRAINT anomaly_class_project_code_unique IF NOT EXISTS
FOR (anomaly:AnomalyClass)
REQUIRE (anomaly.project_id, anomaly.code) IS UNIQUE;

CREATE INDEX part_type_index IF NOT EXISTS
FOR (part:Part)
ON (part.part_type);

CREATE INDEX process_run_anomaly_index IF NOT EXISTS
FOR (run:ProcessRun)
ON (run.anomaly);

CREATE INDEX measurement_feature_qc_index IF NOT EXISTS
FOR (measurement:QualityMeasurement)
ON (measurement.feature, measurement.qc_pass);
