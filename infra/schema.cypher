// P3 CiP-DMD MVP schema for Neo4j 5.x
// Idempotent: safe to run more than once.

CREATE CONSTRAINT part_id_unique IF NOT EXISTS
FOR (part:Part)
REQUIRE part.part_id IS UNIQUE;

CREATE CONSTRAINT process_name_unique IF NOT EXISTS
FOR (process:Process)
REQUIRE process.name IS UNIQUE;

CREATE CONSTRAINT process_run_id_unique IF NOT EXISTS
FOR (run:ProcessRun)
REQUIRE run.run_id IS UNIQUE;

CREATE CONSTRAINT measurement_id_unique IF NOT EXISTS
FOR (measurement:QualityMeasurement)
REQUIRE measurement.measurement_id IS UNIQUE;

CREATE CONSTRAINT equipment_id_unique IF NOT EXISTS
FOR (equipment:Equipment)
REQUIRE equipment.equipment_id IS UNIQUE;

CREATE CONSTRAINT anomaly_class_code_unique IF NOT EXISTS
FOR (anomaly:AnomalyClass)
REQUIRE anomaly.code IS UNIQUE;

CREATE INDEX part_type_index IF NOT EXISTS
FOR (part:Part)
ON (part.part_type);

CREATE INDEX process_run_anomaly_index IF NOT EXISTS
FOR (run:ProcessRun)
ON (run.anomaly);

CREATE INDEX measurement_feature_qc_index IF NOT EXISTS
FOR (measurement:QualityMeasurement)
ON (measurement.feature, measurement.qc_pass);
