-- One row per cloud sub-account (team workspace).
select
    sub_account_id,
    any_value(sub_account_name) as sub_account_name,
    any_value(team)             as team,
    any_value(environment)      as environment,
    any_value(provider_name)    as provider_name
from {{ ref('stg_focus_billing') }}
group by sub_account_id
