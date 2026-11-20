"""Compare an agent result against gold rows. Kept separate so it can be unit-tested."""
from __future__ import annotations

import re
from typing import Any

REL_TOL = 0.005  # 0.5%
_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(REL_TOL * abs(b), 0.01)


def _norm(v: Any) -> str:
    return str(v).strip().lower()


def result_matches(compare: str, gold_rows: list[list[Any]], rows: list[list[Any]], sql: str | None) -> bool:
    """Execution accuracy: does the agent's query result contain the gold answer?"""
    if compare == "refuse":
        return sql is None
    if not rows or not gold_rows:
        return False
    if compare == "scalar":
        gold = gold_rows[0][0]
        return any(_is_number(v) and _close(float(v), float(gold)) for row in rows[:5] for v in row)
    if compare == "top1":
        gold = _norm(gold_rows[0][0])
        return any(_norm(v) == gold for v in rows[0])
    if compare == "set":
        gold = {_norm(r[0]) for r in gold_rows}
        return any({_norm(r[i]) for r in rows} == gold for i in range(len(rows[0])))
    raise ValueError(f"Unknown compare type: {compare}")


def answer_mentions(compare: str, gold_rows: list[list[Any]], answer: str) -> bool:
    """Answer faithfulness: does the final text state the gold value?"""
    text = answer.lower()
    if compare == "refuse":
        return bool(text)
    if not gold_rows:
        return False
    if compare == "scalar":
        gold = float(gold_rows[0][0])
        nums = [float(n.replace(",", "")) for n in _NUMBER.findall(answer) if n.replace(",", "") not in ("", "-")]
        return any(_close(n, gold) or _close(n, abs(gold)) for n in nums)
    values = [gold_rows[0][0]] if compare == "top1" else [r[0] for r in gold_rows]
    return all(_mentions_value(v, text) for v in values)


def _mentions_value(v: Any, text: str) -> bool:
    s = _norm(v)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):  # dates: accept 2026-08-01, "august 2026", "aug 15"
        import datetime as dt

        d = dt.date.fromisoformat(s)
        month = d.strftime("%B").lower()
        return s in text or (month in text and (str(d.year) in text or str(d.day) in text))
    return s in text
