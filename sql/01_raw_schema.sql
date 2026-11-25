CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id BIGINT PRIMARY KEY CHECK (customer_id > 0),
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    signup_date DATE NOT NULL,
    source_batch_id INTEGER NOT NULL CHECK (source_batch_id > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.products (
    product_id BIGINT PRIMARY KEY CHECK (product_id > 0),
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    brand TEXT NOT NULL,
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price > 0),
    source_batch_id INTEGER NOT NULL CHECK (source_batch_id > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id BIGINT PRIMARY KEY CHECK (order_id > 0),
    customer_id BIGINT NOT NULL REFERENCES raw.customers(customer_id),
    order_date TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('cancelled', 'delivered', 'pending', 'processing', 'shipped')
    ),
    total_amount NUMERIC(12, 2) NOT NULL CHECK (total_amount >= 0),
    source_batch_id INTEGER NOT NULL CHECK (source_batch_id > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS raw.order_items (
    order_item_id BIGINT PRIMARY KEY CHECK (order_item_id > 0),
    order_id BIGINT NOT NULL REFERENCES raw.orders(order_id),
    product_id BIGINT NOT NULL REFERENCES raw.products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(10, 2) NOT NULL CHECK (unit_price > 0),
    source_batch_id INTEGER NOT NULL CHECK (source_batch_id > 0),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_orders_customer_id ON raw.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_raw_orders_order_date ON raw.orders(order_date);
CREATE INDEX IF NOT EXISTS idx_raw_order_items_order_id ON raw.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_raw_order_items_product_id ON raw.order_items(product_id);
