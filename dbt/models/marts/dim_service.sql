-- One row per cloud service, excluding tax pseudo-services.
select
    service_name,
    any_value(service_category) as service_category,
    any_value(provider_name)    as provider_name
from {{ ref('stg_focus_billing') }}
where charge_category = 'Usage'
group by service_name
