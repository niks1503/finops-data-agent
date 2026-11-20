from finops_agent.tools import Toolbox


def test_run_sql_returns_rows():
    out = Toolbox().call("run_sql", {"sql": "select count(*) as n from dim_account"})
    assert out["columns"] == ["n"] and out["rows"] == [[8]]


def test_run_sql_returns_errors_for_self_correction():
    out = Toolbox().call("run_sql", {"sql": "select missing_col from dim_account"})
    assert "error" in out and "missing_col" in out["error"]


def test_guard_errors_are_returned_not_raised():
    out = Toolbox().call("run_sql", {"sql": "drop table dim_account"})
    assert out["error"].startswith("Rejected by SQL guard")


def test_connection_is_read_only():
    tb = Toolbox()
    try:
        tb.con.execute("create table hack as select 1")
        raised = False
    except Exception:
        raised = True
    assert raised


def test_schema_search_finds_relevant_table():
    hits = Toolbox().index.search("monthly cost change for a service month over month", k=1)
    assert hits[0].startswith("TABLE mart_monthly_cost")


def test_unknown_tool():
    assert "error" in Toolbox().call("delete_everything", {})
