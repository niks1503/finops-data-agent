from finops_agent.agent import FinOpsAgent
from finops_agent.llm import LLMTurn, ScriptedLLM, ToolCall

GOOD_SQL = (
    "select a.sub_account_name, sum(f.effective_cost) as cost from fct_daily_cost f "
    "join dim_account a using (sub_account_id) where f.billing_month = date '2026-10-01' "
    "group by 1 order by 2 desc limit 1"
)


def test_agent_self_corrects_after_sql_error():
    llm = ScriptedLLM([
        LLMTurn(tool_calls=[ToolCall("search_schema", {"query": "cost by account"})], input_tokens=100, output_tokens=10),
        LLMTurn(tool_calls=[ToolCall("run_sql", {"sql": "select account_name from dim_account"})]),
        LLMTurn(tool_calls=[ToolCall("run_sql", {"sql": GOOD_SQL})]),
        LLMTurn(text="payments-prod spent the most in October 2026 (28,543.22 USD).", input_tokens=50, output_tokens=20),
    ])
    r = FinOpsAgent(llm=llm).ask("Which account spent the most last month?")

    assert r.error is None
    assert r.sql_attempts == 2 and r.sql_errors == 1
    assert r.sql == GOOD_SQL
    assert r.rows[0][0] == "payments-prod"
    assert "payments-prod" in r.answer
    assert r.input_tokens == 150 and r.output_tokens == 30
    # the SQL error was sent back to the model so it could fix the query
    sent_results = [m for m in llm.received if m[0] == "tool_results"]
    assert "error" in sent_results[1][1][0][1]


def test_agent_refusal_runs_no_sql():
    llm = ScriptedLLM([LLMTurn(text="I can only read cost data, so I can't delete anything.")])
    r = FinOpsAgent(llm=llm).ask("Delete all dev rows")
    assert r.sql is None and r.sql_attempts == 0 and "can't" in r.answer


def test_agent_stops_at_step_limit():
    loop = [LLMTurn(tool_calls=[ToolCall("search_schema", {"query": "x"})]) for _ in range(5)]
    r = FinOpsAgent(llm=ScriptedLLM(loop), max_steps=3).ask("loop forever")
    assert r.error == "max_steps_exceeded"


def test_agent_asks_again_when_final_reply_is_empty():
    llm = ScriptedLLM([
        LLMTurn(tool_calls=[ToolCall("run_sql", {"sql": "select count(*) from dim_account"})]),
        LLMTurn(text="_"),  # empty-looking final reply
        LLMTurn(text="There are 8 accounts."),
    ])
    r = FinOpsAgent(llm=llm).ask("How many accounts?")
    assert r.answer == "There are 8 accounts."
    assert ("user", "Please state the answer to my question in 1-3 sentences, using only the query results.") in llm.received
