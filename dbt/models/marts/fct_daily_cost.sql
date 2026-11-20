-- Grain: one row per charge_date, sub-account, service, region and charge category.
select
    charge_date,
    billing_period_start                 as billing_month,
    sub_account_id,
    service_name,
    service_category,
    region_id,
    charge_category,
    sum(consumed_quantity)               as consumed_quantity,
    any_value(consumed_unit)             as consumed_unit,
    sum(list_cost)                       as list_cost,
    sum(billed_cost)                     as billed_cost,
    sum(effective_cost)                  as effective_cost
from {{ ref('stg_focus_billing') }}
group by all
