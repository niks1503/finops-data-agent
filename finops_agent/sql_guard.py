"""Guardrails that make sure the agent can only run a single read-only SELECT."""
from __future__ import annotations

import re

import duckdb


class UnsafeSQLError(ValueError):
    """Raised when generated SQL is not a single, read-only SELECT."""


_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|attach|detach|copy|pragma|install|load|export|import|"
    r"call|set|reset|truncate|grant|revoke|vacuum|checkpoint|merge|"
    r"read_csv|read_csv_auto|read_parquet|read_json|read_json_auto|read_text|read_blob|glob)\b",
    re.IGNORECASE,
)
_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")


def validate_and_limit(sql: str, max_rows: int = 200) -> str:
    """Return a safe, row-limited version of `sql`, or raise UnsafeSQLError."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQLError("Empty query.")

    try:
        statements = duckdb.extract_statements(cleaned)
    except duckdb.Error as exc:  # syntax errors are reported back to the agent so it can fix them
        raise UnsafeSQLError(f"SQL could not be parsed: {exc}") from exc
    if len(statements) != 1:
        raise UnsafeSQLError("Only one statement is allowed per query.")
    if statements[0].type != duckdb.StatementType.SELECT:
        raise UnsafeSQLError("Only SELECT queries are allowed.")

    # Scan for dangerous keywords outside string literals (so WHERE name = 'Delete' is fine).
    match = _FORBIDDEN.search(_STRING_LITERAL.sub("''", cleaned))
    if match:
        raise UnsafeSQLError(f"Keyword or function '{match.group(0)}' is not allowed.")

    return f"SELECT * FROM (\n{cleaned}\n) AS agent_query LIMIT {int(max_rows)}"
