select
    order_item_id::bigint as order_item_id,
    order_id::bigint as order_id,
    product_id::bigint as product_id,
    quantity::integer as quantity,
    unit_price::numeric(10, 2) as unit_price,
    source_batch_id::integer as source_batch_id,
    ingested_at::timestamptz as ingested_at
from {{ source('raw', 'order_items') }}
