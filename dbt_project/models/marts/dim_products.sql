{{ config(
    unique_key='product_id',
    on_schema_change='sync_all_columns'
) }}

select
    product_id,
    product_name,
    category,
    brand,
    unit_price,
    source_batch_id,
    ingested_at
from {{ ref('stg_products') }}
{% if is_incremental() %}
where ingested_at >= (
    select coalesce(max(ingested_at), '1900-01-01'::timestamptz)
    from {{ this }}
)
{% endif %}
