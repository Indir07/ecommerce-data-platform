{{ config(
    unique_key='order_id',
    on_schema_change='sync_all_columns'
) }}

with item_totals as (
    select
        order_id,
        count(*)::integer as item_count,
        sum(line_amount)::numeric(14, 2) as items_subtotal
    from {{ ref('int_order_items') }}
    group by order_id
)

select
    orders.order_id,
    orders.customer_id,
    orders.order_date,
    orders.status,
    orders.total_amount,
    coalesce(item_totals.item_count, 0)::integer as item_count,
    coalesce(item_totals.items_subtotal, 0)::numeric(14, 2) as items_subtotal,
    orders.source_batch_id,
    orders.ingested_at
from {{ ref('stg_orders') }} as orders
left join item_totals
    on orders.order_id = item_totals.order_id
{% if is_incremental() %}
where orders.ingested_at >= (
    select coalesce(max(ingested_at), '1900-01-01'::timestamptz)
    from {{ this }}
)
{% endif %}
