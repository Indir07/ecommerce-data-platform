select
    order_id::bigint as order_id,
    customer_id::bigint as customer_id,
    order_date::timestamptz as order_date,
    status,
    total_amount::numeric(12, 2) as total_amount,
    source_batch_id::integer as source_batch_id,
    ingested_at::timestamptz as ingested_at
from {{ source('raw', 'orders') }}
