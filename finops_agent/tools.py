"""Tools the agent can call: schema search over dbt docs, and read-only SQL execution."""
from __future__ import annotations

import datetime as dt
import decimal
from pathlib import Path
from typing import Any

import duckdb

from .config import settings
from .schema_docs import SchemaIndex
from .sql_guard import UnsafeSQLError, validate_and_limit

ROWS_SHOWN_TO_MODEL = 50


def connect(db_path: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open the warehouse read-only, with file and network access disabled."""
    return duckdb.connect(
        str(db_path or settings.db_path),
        read_only=True,
        config={"enable_external_access": False},
    )


def _jsonable(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, float):
        return round(value, 4)
    return value


def run_sql(con: duckdb.DuckDBPyConnection, sql: str, max_rows: int | None = None) -> dict[str, Any]:
    """Validate and execute a SELECT. Returns columns/rows, or an error message the model can act on."""
    try:
        safe_sql = validate_and_limit(sql, max_rows or settings.max_rows)
    except UnsafeSQLError as exc:
        return {"error": f"Rejected by SQL guard: {exc}"}
    try:
        cur = con.execute(safe_sql)
        columns = [d[0] for d in cur.description]
        rows = [[_jsonable(v) for v in row] for row in cur.fetchall()]
    except duckdb.Error as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}
    return {
        "columns": columns,
        "rows": rows[:ROWS_SHOWN_TO_MODEL],
        "row_count": len(rows),
        "truncated": len(rows) > ROWS_SHOWN_TO_MODEL,
    }


class Toolbox:
    """Bundles the tools with their JSON schemas for the LLM."""

    SPECS = [
        {
            "name": "search_schema",
            "description": (
                "Search the documented warehouse schema (dbt models). Returns the most relevant tables "
                "with column names, types and descriptions. Call this before writing SQL."
            ),
            "parameters_json_schema": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "What data you need, in plain words."}},
                "required": ["query"],
            },
        },
        {
            "name": "run_sql",
            "description": (
                "Run ONE read-only DuckDB SELECT (CTEs allowed) and get the result rows. "
                "If it returns an error, read it, fix the SQL and call run_sql again."
            ),
            "parameters_json_schema": {
                "type": "object",
                "properties": {"sql": {"type": "string", "description": "A single DuckDB SELECT statement."}},
                "required": ["sql"],
            },
        },
    ]

    def __init__(self, con: duckdb.DuckDBPyConnection | None = None, index: SchemaIndex | None = None):
        self.con = con or connect()
        self.index = index or SchemaIndex.from_manifest(self.con)

    def call(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name == "search_schema":
            return {"tables": self.index.search(str(args.get("query", "")))}
        if name == "run_sql":
            return run_sql(self.con, str(args.get("sql", "")))
        return {"error": f"Unknown tool '{name}'."}
