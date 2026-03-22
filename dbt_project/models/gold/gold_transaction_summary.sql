{{
    config(materialized='table')
}}

with daily_transactions as (
    select
        cast(date_trunc('day', event_timestamp) as date)    as summary_date,
        account_id,
        transaction_type,
        amount,
        is_suspicious
    from {{ ref('silver_transactions_clean') }}
)

select
    summary_date,
    account_id,
    count(*)                                                        as transaction_count,
    sum(case when transaction_type = 'CREDIT' then amount else 0 end)   as total_credit,
    sum(case when transaction_type = 'DEBIT'  then amount else 0 end)   as total_debit,
    sum(case when is_suspicious then 1 else 0 end)                  as suspicious_count
from daily_transactions
group by summary_date, account_id
