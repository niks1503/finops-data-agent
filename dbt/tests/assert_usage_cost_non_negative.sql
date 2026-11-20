-- Usage charges must never be negative; only Credit rows may be.
select *
from {{ ref('fct_daily_cost') }}
where charge_category = 'Usage' and effective_cost < 0
