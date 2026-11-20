"""The agent loop: search schema -> write SQL -> run -> self-correct -> answer from results only."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any

from .config import settings
from .llm import GeminiClient, LLMClient
from .tools import Toolbox

SYSTEM_PROMPT = """You are a FinOps analyst assistant. You answer questions about cloud cost and usage
by querying a DuckDB warehouse. The data covers 2025-11-01 to 2026-10-31; "last month" means October 2026.

Available tables:
{overview}

How to work:
1. Call search_schema to see the columns of the tables you need.
2. Write ONE DuckDB SELECT and call run_sql.
3. If run_sql returns an error or an obviously wrong result, fix the SQL and call run_sql again.
4. Answer in 1-3 sentences using ONLY numbers that appear in the query results. Money is USD,
   rounded to 2 decimals. Months are DATE values for the first of the month (e.g. DATE '2026-09-01').

Rules:
- Use effective_cost for "cost" or "spend" unless the user asks for billed or list cost.
- "Usage cost" or "usage spend" means charge_category = 'Usage' only (exclude Tax and Credit rows).
  Tax and Credit rows are dated the first day of the month, so they distort daily figures.
- Join to dim_account to filter or label by account name or team.
- Never invent numbers. If the data cannot answer the question, say so.
- You can only read data. If asked to change, delete or create anything, or to answer something
  unrelated to the cloud cost data, politely refuse without running SQL.
"""


@dataclass
class AgentResult:
    question: str
    answer: str = ""
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    steps: list[dict[str, Any]] = field(default_factory=list)
    sql_attempts: int = 0
    sql_errors: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    model: str = ""
    error: str | None = None

    @property
    def cost_usd(self) -> float:
        return (self.input_tokens * settings.price_in_per_m + self.output_tokens * settings.price_out_per_m) / 1e6

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "cost_usd": self.cost_usd}


class FinOpsAgent:
    def __init__(self, llm: LLMClient | None = None, toolbox: Toolbox | None = None, max_steps: int | None = None):
        self.llm = llm or GeminiClient(
            settings.gemini_api_key, settings.gemini_model, list(settings.gemini_fallbacks), settings.gemini_timeout_s
        )
        self.tools = toolbox or Toolbox()
        self.max_steps = max_steps or settings.max_steps
        self.system = SYSTEM_PROMPT.format(overview=self.tools.index.overview())

    def ask(self, question: str) -> AgentResult:
        result = AgentResult(question=question, model=self.llm.model)
        start = time.perf_counter()
        try:
            session = self.llm.new_session(self.system, Toolbox.SPECS)
            turn = session.send_user(question)
            nudged = False
            for _ in range(self.max_steps):
                result.input_tokens += turn.input_tokens
                result.output_tokens += turn.output_tokens
                if turn.model:
                    result.model = turn.model
                if not turn.tool_calls:
                    answer = turn.text.strip()
                    if not any(ch.isalnum() for ch in answer) and not nudged:
                        # Models occasionally end with an empty reply after a successful query: ask once more.
                        nudged = True
                        turn = session.send_user(
                            "Please state the answer to my question in 1-3 sentences, using only the query results."
                        )
                        continue
                    result.answer = answer or "I couldn't produce an answer for that question."
                    break
                outputs = []
                for call in turn.tool_calls:
                    output = self.tools.call(call.name, call.args)
                    self._record(result, call.name, call.args, output)
                    outputs.append((call, output))
                turn = session.send_tool_results(outputs)
            else:
                result.answer = "I couldn't reach a reliable answer within the step limit."
                result.error = "max_steps_exceeded"
        except Exception as exc:  # surface provider errors in the result instead of crashing the API/UI
            result.error = f"{type(exc).__name__}: {exc}"
            result.answer = result.answer or "Sorry, something went wrong while answering."
        result.latency_s = round(time.perf_counter() - start, 3)
        return result

    @staticmethod
    def _record(result: AgentResult, name: str, args: dict[str, Any], output: dict[str, Any]) -> None:
        step: dict[str, Any] = {"tool": name, "args": args}
        if name == "run_sql":
            result.sql_attempts += 1
            if "error" in output:
                result.sql_errors += 1
                step["error"] = output["error"]
            else:
                result.sql = args.get("sql")
                result.columns, result.rows = output["columns"], output["rows"]
                step["row_count"] = output["row_count"]
        result.steps.append(step)
