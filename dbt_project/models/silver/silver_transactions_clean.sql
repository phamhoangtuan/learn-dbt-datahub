{{
    config(materialized='table')
}}

with parsed as (
    select
        data->>'event_id'                               as event_id,
        data->>'event_type'                             as event_type,
        cast(data->>'event_timestamp' as timestamp)     as event_timestamp,
        data->>'transaction_id'                         as transaction_id,
        data->>'account_id'                             as account_id,
        data->>'transaction_type'                       as transaction_type,
        cast(data->>'amount' as double)                 as amount,
        data->>'currency'                               as currency,
        data->>'description'                            as description,
        data->>'target_account_id'                      as target_account_id,
        data->>'status'                                 as status
    from {{ ref('bronze_transactions_raw') }}
)

select
    event_id,
    event_type,
    event_timestamp,
    transaction_id,
    account_id,
    transaction_type,
    amount,
    currency,
    description,
    target_account_id,
    status,
    {{ is_suspicious_transaction('amount', 'status') }} as is_suspicious
from parsed
