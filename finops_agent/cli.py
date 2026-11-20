"""Ask the agent a question from the terminal: python -m finops_agent.cli "Why did storage cost jump?" """
from __future__ import annotations

import sys

from .agent import FinOpsAgent


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Which account spent the most last month?"
    r = FinOpsAgent().ask(question)
    print(f"\nQ: {question}\nA: {r.answer}\n")
    if r.sql:
        print(f"SQL:\n{r.sql}\n")
    print(f"[{r.model}] {r.latency_s}s | SQL attempts {r.sql_attempts} (errors {r.sql_errors}) | "
          f"tokens {r.input_tokens}+{r.output_tokens}" + (f" | error: {r.error}" if r.error else ""))


if __name__ == "__main__":
    main()
