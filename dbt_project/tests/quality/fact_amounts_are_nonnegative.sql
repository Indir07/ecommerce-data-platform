select order_id
from {{ ref('fact_orders') }}
where total_amount < 0
   or items_subtotal < 0
   or item_count < 0
