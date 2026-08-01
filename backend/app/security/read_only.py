"""Conservative read-only checks applied before EXPLAIN and execution."""

from __future__ import annotations

import re


WRITE_PATTERNS = {
    "CREATE": r"\bCREATE\b",
    "MERGE": r"\bMERGE\b",
    "DELETE": r"\bDELETE\b",
    "DETACH DELETE": r"\bDETACH\s+DELETE\b",
    "SET": r"\bSET\b",
    "REMOVE": r"\bREMOVE\b",
    "DROP": r"\bDROP\b",
    "LOAD CSV": r"\bLOAD\s+CSV\b",
    "FOREACH": r"\bFOREACH\b",
    "GRANT": r"\bGRANT\b",
    "DENY": r"\bDENY\b",
    "REVOKE": r"\bREVOKE\b",
    "ALTER": r"\bALTER\b",
    "RENAME": r"\bRENAME\b",
    "START": r"\bSTART\b",
    "STOP": r"\bSTOP\b",
    "TERMINATE": r"\bTERMINATE\b",
}
DISALLOWED_COMMAND_PATTERNS = {
    "CALL": r"\bCALL\b",
    "USE": r"\bUSE\b",
    "SHOW": r"\bSHOW\b",
    "PROFILE": r"\bPROFILE\b",
    "EXPLAIN": r"\bEXPLAIN\b",
    "APOC": r"\bAPOC\.",
    "DBMS": r"\bDBMS\.",
}
ALLOWED_START = re.compile(
    r"^\s*(MATCH|OPTIONAL\s+MATCH|WITH|UNWIND|RETURN)\b",
    re.IGNORECASE,
)
WRITE_REQUEST = re.compile(
    r"(삭제|지워|수정해|바꿔|생성해|추가해|저장해|"
    r"\bdelete\b|\bremove\b|\bcreate\b|\bupdate\b|\bwrite\b)",
    re.IGNORECASE,
)
AMBIGUOUS_REQUEST = re.compile(
    r"^\s*(?:문제|이상|불량)(?:가|이)?\s*(?:있는\s*)?"
    r"(?:부품|제품)(?:을|를)?\s*(?:찾아|보여)(?:줘|주세요)?"
    r"[.!?]?\s*$",
    re.IGNORECASE,
)


def _strip_literals_and_comments(statement: str) -> str:
    output: list[str] = []
    index = 0
    state = "normal"
    while index < len(statement):
        char = statement[index]
        following = statement[index + 1] if index + 1 < len(statement) else ""
        if state == "normal":
            if char == "/" and following == "/":
                state = "line_comment"
                output.extend("  ")
                index += 2
                continue
            if char == "/" and following == "*":
                state = "block_comment"
                output.extend("  ")
                index += 2
                continue
            if char in {"'", '"', "`"}:
                state = {"'": "single", '"': "double", "`": "backtick"}[char]
                output.append(" ")
            else:
                output.append(char)
        elif state == "line_comment":
            if char == "\n":
                state = "normal"
                output.append("\n")
            else:
                output.append(" ")
        elif state == "block_comment":
            if char == "*" and following == "/":
                state = "normal"
                output.extend("  ")
                index += 2
                continue
            output.append(" ")
        else:
            closing = {"single": "'", "double": '"', "backtick": "`"}[state]
            if char == "\\" and following:
                output.extend("  ")
                index += 2
                continue
            if char == closing:
                state = "normal"
            output.append(" ")
        index += 1
    return "".join(output)


def detect_write_request(question: str) -> bool:
    return bool(WRITE_REQUEST.search(question))


def detect_ambiguous_request(question: str) -> bool:
    return bool(AMBIGUOUS_REQUEST.search(question))


def validate_read_only(statement: str) -> list[str]:
    if not statement.strip():
        return ["EMPTY_QUERY: The model returned no Cypher statement."]

    scrubbed = _strip_literals_and_comments(statement)
    errors: list[str] = []
    body = scrubbed.strip()
    if ";" in body.rstrip(";"):
        errors.append("MULTIPLE_STATEMENTS: Only one Cypher statement is allowed.")
    if not ALLOWED_START.search(body):
        errors.append(
            "INVALID_START: Query must begin with MATCH, OPTIONAL MATCH, "
            "WITH, UNWIND, or RETURN."
        )
    for name, pattern in WRITE_PATTERNS.items():
        if re.search(pattern, scrubbed, re.IGNORECASE):
            errors.append(f"WRITE_CLAUSE: {name} is not allowed.")
    for name, pattern in DISALLOWED_COMMAND_PATTERNS.items():
        if re.search(pattern, scrubbed, re.IGNORECASE):
            errors.append(f"DISALLOWED_COMMAND: {name} is not allowed.")
    return list(dict.fromkeys(errors))


def ensure_read_only(statement: str) -> None:
    errors = validate_read_only(statement)
    if errors:
        raise ValueError(" ".join(errors))
