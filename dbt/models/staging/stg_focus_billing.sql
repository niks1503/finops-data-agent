-- Clean, typed, snake_case view over the raw FOCUS billing export.
select
    cast(BillingPeriodStart as date)  as billing_period_start,
    cast(ChargePeriodStart as date)   as charge_date,
    ChargeCategory                    as charge_category,
    ProviderName                      as provider_name,
    SubAccountId                      as sub_account_id,
    SubAccountName                    as sub_account_name,
    ServiceName                       as service_name,
    ServiceCategory                   as service_category,
    SkuId                             as sku_id,
    RegionId                          as region_id,
    RegionName                        as region_name,
    ResourceId                        as resource_id,
    cast(ConsumedQuantity as double)  as consumed_quantity,
    ConsumedUnit                      as consumed_unit,
    cast(ListCost as double)          as list_cost,
    cast(BilledCost as double)        as billed_cost,
    cast(EffectiveCost as double)     as effective_cost,
    BillingCurrency                   as billing_currency,
    json_extract_string(Tags, '$.team')        as team,
    json_extract_string(Tags, '$.environment') as environment
from {{ source('raw', 'focus_billing') }}
