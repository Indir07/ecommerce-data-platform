select
    product_id::bigint as product_id,
    product_name,
    category,
    brand,
    unit_price::numeric(10, 2) as unit_price,
    source_batch_id::integer as source_batch_id,
    ingested_at::timestamptz as ingested_at
from {{ source('raw', 'products') }}
