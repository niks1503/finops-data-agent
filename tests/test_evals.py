import pytest
from compare import answer_mentions, result_matches
from run_evals import gold_rows, load_cases

from finops_agent.tools import connect


@pytest.mark.parametrize("case", load_cases(), ids=lambda c: c["id"])
def test_gold_sql_runs_and_returns_rows(case):
    rows = gold_rows(connect(), case)
    assert case["compare"] == "refuse" or rows


def test_scalar_tolerance():
    assert result_matches("scalar", [[100.0]], [["x", 100.3]], "select")
    assert not result_matches("scalar", [[100.0]], [[101.0]], "select")


def test_top1_and_set():
    assert result_matches("top1", [["payments-prod", 1.0]], [["Payments-Prod", 2.0]], "select")
    assert result_matches("set", [["a"], ["b"]], [[1, "b"], [2, "a"]], "select")
    assert not result_matches("set", [["a"], ["b"]], [["a"]], "select")


def test_refusal_means_no_query():
    assert result_matches("refuse", [], [], None)
    assert not result_matches("refuse", [], [[1]], "select 1")


def test_answer_mentions_numbers_and_dates():
    assert answer_mentions("scalar", [[28543.2204]], "It was $28,543.22 in October.")
    assert answer_mentions("top1", [["2026-08-01", 1]], "Vertex AI peaked in August 2026.")
    assert not answer_mentions("scalar", [[100.0]], "About two hundred dollars.")
