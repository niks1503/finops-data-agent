import pytest

from finops_agent.sql_guard import UnsafeSQLError, validate_and_limit


@pytest.mark.parametrize("sql", [
    "select 1",
    "with t as (select 1 as x) select x from t",
    "select * from dim_account where sub_account_name = 'delete-me';",
])
def test_allows_read_only_selects(sql):
    out = validate_and_limit(sql, max_rows=10)
    assert out.endswith("LIMIT 10")


@pytest.mark.parametrize("sql", [
    "drop table dim_account",
    "delete from fct_daily_cost",
    "insert into dim_account values ('x')",
    "update dim_account set team = 'x'",
    "create table t as select 1",
    "select 1; drop table dim_account",
    "attach 'other.db'",
    "copy dim_account to 'out.csv'",
    "select * from read_csv_auto('/etc/passwd')",
    "select * from read_parquet('s3://bucket/x.parquet')",
    "pragma database_list",
    "",
])
def test_blocks_writes_multi_statements_and_file_access(sql):
    with pytest.raises(UnsafeSQLError):
        validate_and_limit(sql)


def test_reports_syntax_errors_as_unsafe_sql():
    with pytest.raises(UnsafeSQLError, match="parsed"):
        validate_and_limit("selec * fro dim_account")
