select
    item.order_item_id,
    item.order_id,
    item.product_id,
    item.quantity,
    item.unit_price,
    (item.quantity * item.unit_price)::numeric(14, 2) as line_amount,
    item.source_batch_id,
    item.ingested_at
from {{ ref('stg_order_items') }} as item
