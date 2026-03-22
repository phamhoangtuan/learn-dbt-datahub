{{
    config(materialized='table')
}}

select
    replace(data, concat(chr(92), chr(34)), chr(34)) as data
from TRANSACTIONS_RAW
