{{ config(
    unique_key='customer_id',
    on_schema_change='sync_all_columns'
) }}

select
    customer_id,
    first_name,
    last_name,
    email,
    city,
    signup_date,
    source_batch_id,
    ingested_at
from {{ ref('stg_customers') }}
{% if is_incremental() %}
where ingested_at >= (
    select coalesce(max(ingested_at), '1900-01-01'::timestamptz)
    from {{ this }}
)
{% endif %}
