select
    customer_id::bigint as customer_id,
    first_name,
    last_name,
    email,
    city,
    signup_date::date as signup_date,
    source_batch_id::integer as source_batch_id,
    ingested_at::timestamptz as ingested_at
from {{ source('raw', 'customers') }}
