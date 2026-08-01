"""Deterministic domain and question-to-query checks beyond EXPLAIN."""

from __future__ import annotations

import re


EQUIPMENT_IDS = {"kasto-sba-2", "dmc-50h", "index-c65"}
EQUIPMENT_NAMES = {"Kasto SBA 2", "DMC 50H", "Index C65"}


def _property_literals(statement: str, property_name: str) -> list[str]:
    pattern = rf"\b{re.escape(property_name)}\s*:\s*(['\"])(.*?)\1"
    return [
        match.group(2)
        for match in re.finditer(pattern, statement, re.IGNORECASE)
    ]


def validate_domain_semantics(
    question: str, statement: str
) -> list[str]:
    errors: list[str] = []
    for value in _property_literals(statement, "equipment_id"):
        if value not in EQUIPMENT_IDS:
            errors.append(
                "DOMAIN_VALUE: Equipment.equipment_id must use a slug "
                f"{sorted(EQUIPMENT_IDS)}; display value {value!r} belongs "
                "in Equipment.name."
            )
    for value in _property_literals(statement, "name"):
        if value in EQUIPMENT_IDS:
            errors.append(
                "DOMAIN_VALUE: Equipment.name must use its display name; "
                f"slug {value!r} belongs in Equipment.equipment_id."
            )
    if "역할" in question and "component_role" not in statement:
        errors.append(
            "QUESTION_ALIGNMENT: The question asks for the assembly role; "
            "return ASSEMBLED_FROM.component_role."
        )
    if "합격 여부" in question and "qc_pass" not in statement:
        errors.append(
            "QUESTION_ALIGNMENT: The question asks for pass/fail; "
            "return QualityMeasurement.qc_pass."
        )
    invalid_topologies = (
        (
            r"\(\s*(?:\w+\s*)?:\s*Equipment\b[^)]*\)\s*"
            r"-\s*\[\s*:CLASSIFIED_AS\b",
            "SCHEMA_TOPOLOGY: CLASSIFIED_AS must start at ProcessRun, "
            "not Equipment. Match (run)-[:CLASSIFIED_AS]->(anomaly) "
            "as a separate path.",
        ),
        (
            r"\(\s*(?:\w+\s*)?:\s*Equipment\b[^)]*\)\s*"
            r"-\s*\[\s*:INSTANCE_OF\b",
            "SCHEMA_TOPOLOGY: INSTANCE_OF must start at ProcessRun, "
            "not Equipment.",
        ),
    )
    for pattern, message in invalid_topologies:
        if re.search(pattern, statement, re.IGNORECASE | re.DOTALL):
            errors.append(message)
    return errors
