-- Monthly effective cost per sub-account and service, with month-over-month change.
with monthly as (
    select
        f.billing_month,
        f.sub_account_id,
        a.sub_account_name,
        a.team,
        f.service_name,
        f.service_category,
        sum(f.effective_cost) as effective_cost
    from {{ ref('fct_daily_cost') }} f
    join {{ ref('dim_account') }} a using (sub_account_id)
    group by all
)
select
    *,
    lag(effective_cost) over (partition by sub_account_id, service_name order by billing_month) as prev_month_cost,
    effective_cost - lag(effective_cost) over (partition by sub_account_id, service_name order by billing_month) as mom_change,
    round(100.0 * (effective_cost / nullif(lag(effective_cost) over (partition by sub_account_id, service_name order by billing_month), 0) - 1), 2) as mom_change_pct
from monthly
