"""Prompts for generation and correction."""

from __future__ import annotations


def generation_prompt(
    question: str, schema: str, few_shot_examples: str
) -> str:
    return f"""You are a Neo4j Cypher expert for a manufacturing RCA system.
Convert the user question into exactly one read-only Cypher query.

Rules:
- Return Cypher only. Do not use Markdown fences or explanations.
- Begin with MATCH, OPTIONAL MATCH, WITH, UNWIND, or RETURN.
- Use only labels, relationships, and properties in the supplied schema.
- Never use CREATE, MERGE, SET, REMOVE, DELETE, DROP, LOAD CSV, FOREACH,
  procedure calls, administration commands, or multiple statements.
- Do not invent IDs, equipment, anomaly names, or quality values.
- Return identifiers and evidence fields needed to verify the answer.
- Use a sensible LIMIT for unbounded detail queries.
- An empty database result is valid; do not replace it with fabricated data.

Schema:
{schema}

Human-reviewed examples:
{few_shot_examples}

User question:
{question}

Cypher:"""


def correction_prompt(
    question: str,
    schema: str,
    statement: str,
    errors: list[str],
) -> str:
    error_text = "\n".join(f"- {error}" for error in errors)
    return f"""You are correcting a read-only Neo4j Cypher query.
Return one corrected Cypher query only, without Markdown or explanation.
Never add a write clause, procedure call, administration command, or a second statement.
When returning a relationship property, bind the relationship to a variable
(for example, [rel:RELATIONSHIP_TYPE]) and return rel.property_name.
If an unknown identifier came directly from the user question, preserve it as
a read filter so the database can return an honest empty result.

Schema:
{schema}

Original question:
{question}

Rejected query:
{statement}

Validation errors:
{error_text}

Corrected Cypher:"""
