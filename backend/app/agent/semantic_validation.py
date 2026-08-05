"""Deterministic domain and question-to-query checks beyond EXPLAIN."""

from __future__ import annotations

import re
from typing import Any, Callable


EQUIPMENT_IDS = {"kasto-sba-2", "dmc-50h", "index-c65"}
EQUIPMENT_NAMES = {"Kasto SBA 2", "DMC 50H", "Index C65"}


def _property_literals(statement: str, property_name: str) -> list[str]:
    pattern = (
        rf"(?:\b[A-Za-z_]\w*\.)?\b{re.escape(property_name)}"
        rf"\s*(?::|=)\s*(['\"])(.*?)\1"
    )
    return [
        match.group(2)
        for match in re.finditer(pattern, statement, re.IGNORECASE)
    ]


def _labeled_property_literals(
    statement: str,
    label: str,
    property_name: str,
) -> list[str]:
    """Extract literals only when the property belongs to the given label."""

    values: list[str] = []
    aliases: set[str] = set()
    node_pattern = (
        rf"\(\s*(?P<alias>[A-Za-z_]\w*)?\s*"
        rf"(?P<labels>(?::\s*`?[A-Za-z_]\w*`?\s*)+)"
        rf"(?P<body>[^)]*)\)"
    )
    for node in re.finditer(
        node_pattern,
        statement,
        re.IGNORECASE | re.DOTALL,
    ):
        labels = {
            matched.lower()
            for matched in re.findall(
                r":\s*`?([A-Za-z_]\w*)`?",
                node.group("labels"),
            )
        }
        if label.lower() not in labels:
            continue
        if node.group("alias"):
            aliases.add(node.group("alias"))
        inline_pattern = (
            rf"\b{re.escape(property_name)}\s*:\s*"
            rf"(['\"])(.*?)\1"
        )
        values.extend(
            match.group(2)
            for match in re.finditer(
                inline_pattern,
                node.group("body"),
                re.IGNORECASE | re.DOTALL,
            )
        )
    for alias in aliases:
        predicate_pattern = (
            rf"\b{re.escape(alias)}\s*\.\s*`?"
            rf"{re.escape(property_name)}`?\s*=\s*(['\"])(.*?)\1"
        )
        values.extend(
            match.group(2)
            for match in re.finditer(
                predicate_pattern,
                statement,
                re.IGNORECASE,
            )
        )
    return list(dict.fromkeys(values))


def validate_domain_semantics(
    question: str, statement: str
) -> list[str]:
    errors: list[str] = []
    for value in _property_literals(statement, "equipment_id"):
        if (
            value not in EQUIPMENT_IDS
            and (
                value in EQUIPMENT_NAMES
                or value.casefold() not in question.casefold()
            )
        ):
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


def build_domain_validator(
    schema: dict[str, Any],
    *,
    include_cip_rules: bool = False,
) -> Callable[[str, str], list[str]]:
    """Build deterministic property-value checks from a schema manifest."""

    configured: list[tuple[str, str, set[str]]] = []
    identity_properties = {
        (str(node.get("label")), str(node.get("identity")))
        for node in schema.get("nodes") or []
        if node.get("label") and node.get("identity")
    }
    for reference, values in (schema.get("domain_values") or {}).items():
        if "." not in reference:
            continue
        label, property_name = str(reference).split(".", 1)
        configured.append(
            (label, property_name, {str(value) for value in values})
        )

    def validate(question: str, statement: str) -> list[str]:
        errors = (
            validate_domain_semantics(question, statement)
            if include_cip_rules
            else []
        )
        for label, property_name, allowed in configured:
            for value in _labeled_property_literals(
                statement,
                label,
                property_name,
            ):
                if (
                    value not in allowed
                    and not (
                        (label, property_name) in identity_properties
                        and value.casefold() in question.casefold()
                    )
                ):
                    errors.append(
                        f"DOMAIN_VALUE: {label}.{property_name}={value!r} "
                        f"is not stored in this project. Use one of "
                        f"{sorted(allowed)}."
                    )
        return list(dict.fromkeys(errors))

    return validate
