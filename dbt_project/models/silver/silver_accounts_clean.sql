{{
    config(materialized='table')
}}

with parsed as (
    select
        data->>'event_id'                               as event_id,
        data->>'event_type'                             as event_type,
        cast(data->>'event_timestamp' as timestamp)     as event_timestamp,
        data->>'account_id'                             as account_id,
        data->>'customer_id'                            as customer_id,
        data->>'account_type'                           as account_type,
        data->>'status'                                 as status,
        cast(data->>'balance' as double)                as balance,
        data->>'currency'                               as currency
    from {{ ref('bronze_accounts_raw') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by account_id
            order by event_timestamp desc
        ) as rn
    from parsed
)

select
    event_id,
    event_type,
    event_timestamp,
    account_id,
    customer_id,
    account_type,
    status,
    balance,
    currency
from deduped
where rn = 1
