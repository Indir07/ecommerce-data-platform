"""Create reproducible CSV batches with a small, deliberate set of bad records."""

from __future__ import annotations

import argparse
import csv
import random
from datetime import date, datetime, time, timedelta
from pathlib import Path

from ingestion.config import settings

CUSTOMER_FIELDS = [
    "customer_id",
    "first_name",
    "last_name",
    "email",
    "city",
    "signup_date",
]
PRODUCT_FIELDS = [
    "product_id",
    "product_name",
    "category",
    "brand",
    "unit_price",
]
ORDER_FIELDS = [
    "order_id",
    "customer_id",
    "order_date",
    "status",
    "total_amount",
]
ORDER_ITEM_FIELDS = [
    "order_item_id",
    "order_id",
    "product_id",
    "quantity",
    "unit_price",
]

FIRST_NAMES = [
    "Alex", "Avery", "Casey", "Jordan", "Morgan", "Riley", "Sam", "Taylor",
]
LAST_NAMES = [
    "Bennett", "Chen", "Garcia", "Johnson", "Khan", "Martin", "Patel", "Smith",
]
CITIES = [
    "Austin", "Boston", "Chicago", "Denver", "Miami", "Portland", "Seattle",
]
CATEGORIES = [
    "apparel", "beauty", "electronics", "home", "sports",
]
BRANDS = [
    "Acme", "Evergreen", "Northstar", "Summit", "Vertex",
]
STATUSES = [
    "cancelled", "delivered", "pending", "processing", "shipped",
]
BASE_DATE = date(2023, 1, 1)


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def generate_batch(
    batch_id: int,
    output_dir: Path | None = None,
    customer_count: int = 100,
    product_count: int = 30,
    order_count: int = 100,
) -> Path:
    """Write all four source tables for a stable, replayable batch ID."""
    if batch_id < 1:
        raise ValueError("batch_id must be a positive integer")
    if min(customer_count, product_count, order_count) < 2:
        raise ValueError("each entity count must be at least 2")
    if order_count * batch_id * 100_000 > 9_000_000_000_000_000_000:
        raise ValueError("batch_id is too large for generated PostgreSQL identifiers")

    target_dir = (output_dir or settings.data_dir / "raw") / f"batch_{batch_id:08d}"
    rng = random.Random(settings.random_seed + batch_id * 10_000)

    customers: list[dict[str, object]] = []
    for customer_id in range(1, customer_count + 1):
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        signup_date = BASE_DATE + timedelta(days=rng.randrange(1_000))
        customers.append(
            {
                "customer_id": customer_id,
                "first_name": first_name,
                "last_name": last_name,
                "email": f"{first_name.lower()}.{last_name.lower()}.{customer_id}@example.test",
                "city": rng.choice(CITIES),
                "signup_date": signup_date.isoformat(),
            }
        )
    customers[-1]["email"] = ""
    customers.append(dict(customers[0]))

    products: list[dict[str, object]] = []
    for product_id in range(1, product_count + 1):
        products.append(
            {
                "product_id": product_id,
                "product_name": f"{rng.choice(BRANDS)} {rng.choice(CATEGORIES).title()} {product_id:03d}",
                "category": rng.choice(CATEGORIES),
                "brand": rng.choice(BRANDS),
                "unit_price": f"{rng.uniform(5.0, 500.0):.2f}",
            }
        )
    products[-1]["unit_price"] = "-1.00"

    product_prices = {
        int(product["product_id"]): float(product["unit_price"])
        for product in products
        if float(product["unit_price"]) > 0
    }
    orders: list[dict[str, object]] = []
    order_items: list[dict[str, object]] = []
    first_order_id = batch_id * 100_000
    for order_number in range(1, order_count + 1):
        order_id = first_order_id + order_number
        customer_id = rng.randint(1, customer_count - 1)
        order_timestamp = datetime.combine(
            BASE_DATE + timedelta(days=1_000 + batch_id % 365 + rng.randrange(365)),
            time(hour=rng.randrange(24), minute=rng.randrange(60)),
        )
        item_count = rng.randint(1, min(4, product_count - 1))
        order_total = 0.0
        for line_number in range(1, item_count + 1):
            product_id = rng.randint(1, product_count - 1)
            unit_price = product_prices[product_id]
            quantity = rng.randint(1, 5)
            order_total += unit_price * quantity
            order_items.append(
                {
                    "order_item_id": order_id * 10 + line_number,
                    "order_id": order_id,
                    "product_id": product_id,
                    "quantity": quantity,
                    "unit_price": f"{unit_price:.2f}",
                }
            )
        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_date": order_timestamp.isoformat(),
                "status": rng.choice(STATUSES),
                "total_amount": f"{order_total:.2f}",
            }
        )

    order_items[0]["product_id"] = product_count
    orders[-1]["customer_id"] = customer_count + 10_000
    orders[-1]["order_date"] = "not-a-date"
    order_items[-1]["quantity"] = 0

    _write_csv(target_dir / "customers.csv", CUSTOMER_FIELDS, customers)
    _write_csv(target_dir / "products.csv", PRODUCT_FIELDS, products)
    _write_csv(target_dir / "orders.csv", ORDER_FIELDS, orders)
    _write_csv(target_dir / "order_items.csv", ORDER_ITEM_FIELDS, order_items)
    return target_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=settings.data_dir / "raw")
    parser.add_argument("--customers", type=int, default=100)
    parser.add_argument("--products", type=int, default=30)
    parser.add_argument("--orders", type=int, default=100)
    args = parser.parse_args()
    batch_dir = generate_batch(
        args.batch_id, args.output_dir, args.customers, args.products, args.orders
    )
    print(f"Generated batch {args.batch_id} in {batch_dir}")


if __name__ == "__main__":
    main()
