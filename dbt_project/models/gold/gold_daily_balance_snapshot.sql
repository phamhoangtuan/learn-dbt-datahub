{{
    config(materialized='table')
}}

with daily_accounts as (
    select
        cast(date_trunc('day', event_timestamp) as date)    as snapshot_date,
        account_id,
        account_type,
        balance,
        currency,
        status,
        row_number() over (
            partition by account_id, cast(date_trunc('day', event_timestamp) as date)
            order by event_timestamp desc
        ) as rn
    from {{ ref('silver_accounts_clean') }}
)

select
    snapshot_date,
    account_id,
    account_type,
    balance,
    currency,
    status
from daily_accounts
where rn = 1
