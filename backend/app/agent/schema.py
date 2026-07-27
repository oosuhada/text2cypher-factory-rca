"""Canonical schema context supplied to the LLM."""

SCHEMA_CONTEXT = """
Node properties:
Part {part_id: STRING, part_type: STRING, reworked: BOOLEAN, source_file: STRING}
Cylinder extends Part
CylinderBottom extends Part
PistonRod extends Part
Process {name: STRING, display_name: STRING}
Equipment {equipment_id: STRING, name: STRING, equipment_type: STRING}
AnomalyClass {code: STRING, name: STRING, description: STRING, is_normal: BOOLEAN}
ProcessRun {run_id: STRING, sequence: INTEGER, anomaly: STRING,
            start_time: FLOAT, end_time: FLOAT, sensor_file_count: INTEGER}
QualityMeasurement {measurement_id: STRING, feature: STRING,
                    value_text: STRING, value_numeric: FLOAT, qc_pass: BOOLEAN}
QualityFailure extends QualityMeasurement when qc_pass=false

Relationships:
(:Cylinder)-[:ASSEMBLED_FROM {component_role: STRING}]->(:CylinderBottom|PistonRod)
(:Part)-[:UNDERWENT]->(:ProcessRun)
(:ProcessRun)-[:INSTANCE_OF]->(:Process)
(:ProcessRun)-[:RUN_ON]->(:Equipment)
(:ProcessRun)-[:CLASSIFIED_AS]->(:AnomalyClass)
(:Part)-[:HAS_MEASUREMENT]->(:QualityMeasurement)
(:QualityMeasurement)-[:FOR_PROCESS]->(:Process)

Allowed Process.name:
saw, cnc_milling_machine, cnc_lathe, assembly

Allowed AnomalyClass.code:
0, 1, 2, 3

Equipment identity values:
- equipment_id is a slug: kasto-sba-2, dmc-50h, index-c65
- name is a display name: Kasto SBA 2, DMC 50H, Index C65
- When a user says "DMC 50H", match Equipment.name, not equipment_id.

Output contract:
- Return every field explicitly requested by the user.
- If the question asks for a component role, return
  ASSEMBLED_FROM.component_role.
- If the question asks for pass/fail, return QualityMeasurement.qc_pass.
- Keep result aliases concise and based on the requested business term.
""".strip()
