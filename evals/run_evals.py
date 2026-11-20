"""Run the benchmark against the agent and write a report.

    python evals/run_evals.py --validate-gold   # check every gold query (no API key needed)
    python evals/run_evals.py                   # run the agent on all cases
    python evals/run_evals.py --limit 5 --category anomaly
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from compare import answer_mentions, result_matches  # noqa: E402

from finops_agent.tools import connect, run_sql  # noqa: E402

RESULTS_DIR = ROOT / "evals" / "results"


def load_cases(category: str | None = None) -> list[dict]:
    cases = yaml.safe_load((ROOT / "evals" / "benchmark.yaml").read_text())["cases"]
    return [c for c in cases if not category or c["category"] == category]


def gold_rows(con, case: dict) -> list[list]:
    if case["compare"] == "refuse":
        return []
    out = run_sql(con, case["gold_sql"])
    if "error" in out:
        raise RuntimeError(f"Gold SQL failed for {case['id']}: {out['error']}")
    return out["rows"]


def validate_gold() -> int:
    con = connect()
    failures = 0
    for case in load_cases():
        try:
            rows = gold_rows(con, case)
            if case["compare"] != "refuse" and not rows:
                raise RuntimeError("returned no rows")
            shown = "(refusal case)" if case["compare"] == "refuse" else rows[:3]
            print(f"OK   {case['id']:<32} {shown}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {case['id']:<32} {exc}")
    print(f"\n{len(load_cases()) - failures}/{len(load_cases())} gold cases valid")
    return 1 if failures else 0


def run(limit: int | None, category: str | None, delay: float) -> int:
    from finops_agent.agent import FinOpsAgent

    agent = FinOpsAgent()
    con = connect()
    cases = load_cases(category)[:limit] if limit else load_cases(category)
    records = []
    for i, case in enumerate(cases, 1):
        gold = gold_rows(con, case)
        r = agent.ask(case["question"])
        exec_ok = result_matches(case["compare"], gold, r.rows, r.sql)
        ans_ok = answer_mentions(case["compare"], gold, r.answer)
        records.append({
            "id": case["id"], "category": case["category"], "question": case["question"],
            "execution_correct": exec_ok, "answer_correct": ans_ok, "gold": gold[:5], **r.to_dict(),
        })
        mark = "PASS" if exec_ok else "FAIL"
        print(f"[{i}/{len(cases)}] {mark} {case['id']} ({r.latency_s}s, {r.sql_attempts} SQL tries)"
              + (f" error={r.error}" if r.error else ""))
        time.sleep(delay)  # stay inside free-tier rate limits

    summary = summarize(records, agent.llm.model)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "results.json").write_text(json.dumps({"summary": summary, "cases": records}, indent=2, default=str))
    (RESULTS_DIR / "report.md").write_text(render_report(summary, records))
    print(f"\nExecution accuracy: {summary['execution_accuracy']:.1%} | report: evals/results/report.md")
    return 0


def summarize(records: list[dict], model: str) -> dict:
    n = len(records)
    lat = sorted(r["latency_s"] for r in records)
    with_sql = [r for r in records if r["sql_attempts"]]
    by_cat: dict[str, list[bool]] = {}
    for r in records:
        by_cat.setdefault(r["category"], []).append(r["execution_correct"])
    return {
        "model": model,
        "cases": n,
        "execution_accuracy": sum(r["execution_correct"] for r in records) / n,
        "answer_accuracy": sum(r["answer_correct"] for r in records) / n,
        "self_corrected": sum(1 for r in with_sql if r["sql_errors"] and r["execution_correct"]),
        "avg_latency_s": round(statistics.mean(lat), 2),
        "p95_latency_s": round(lat[min(n - 1, int(0.95 * n))], 2),
        "avg_tokens": round(statistics.mean(r["input_tokens"] + r["output_tokens"] for r in records)),
        "avg_cost_usd": round(statistics.mean(r["cost_usd"] for r in records), 6),
        "by_category": {k: round(sum(v) / len(v), 3) for k, v in sorted(by_cat.items())},
    }


def render_report(s: dict, records: list[dict]) -> str:
    lines = [
        f"# Evaluation report ({s['model']})", "",
        "| Metric | Value |", "|---|---|",
        f"| Cases | {s['cases']} |",
        f"| Execution accuracy | {s['execution_accuracy']:.1%} |",
        f"| Answer accuracy | {s['answer_accuracy']:.1%} |",
        f"| Answers rescued by SQL self-correction | {s['self_corrected']} |",
        f"| Avg / p95 latency | {s['avg_latency_s']}s / {s['p95_latency_s']}s |",
        f"| Avg tokens per question | {s['avg_tokens']} |",
        f"| Avg cost per question | ${s['avg_cost_usd']} |", "",
        "## By category", "", "| Category | Execution accuracy |", "|---|---|",
        *[f"| {k} | {v:.0%} |" for k, v in s["by_category"].items()], "",
        "## Failures", "",
    ]
    fails = [r for r in records if not r["execution_correct"]]
    for r in fails:
        lines += [f"### {r['id']}", f"- Q: {r['question']}", f"- Gold: `{r['gold'][:2]}`",
                  f"- Agent rows: `{r['rows'][:2]}`", f"- Answer: {r['answer']}", ""]
    if not fails:
        lines.append("None.")
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--validate-gold", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--category")
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between questions (rate limits)")
    args = ap.parse_args()
    sys.exit(validate_gold() if args.validate_gold else run(args.limit, args.category, args.delay))


if __name__ == "__main__":
    main()
