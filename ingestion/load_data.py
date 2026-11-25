"""Load validated batches into PostgreSQL using idempotent primary-key upserts."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import execute_values

from ingestion.config import PROJECT_ROOT, settings

UPSERTS: dict[str, tuple[list[str], str]] = {
    "customers": (
        ["customer_id", "first_name", "last_name", "email", "city", "signup_date"],
        "customer_id",
    ),
    "products": (
        ["product_id", "product_name", "category", "brand", "unit_price"],
        "product_id",
    ),
    "orders": (
        ["order_id", "customer_id", "order_date", "status", "total_amount"],
        "order_id",
    ),
    "order_items": (
        ["order_item_id", "order_id", "product_id", "quantity", "unit_price"],
        "order_item_id",
    ),
}


def _read_rows(path: Path, fields: list[str]) -> list[tuple[str, ...]]:
    with path.open(newline="", encoding="utf-8") as source:
        return [tuple(row[field] for field in fields) for row in csv.DictReader(source)]


def _upsert_sql(table: str, fields: list[str], key: str) -> str:
    columns = fields + ["source_batch_id"]
    assignments = ", ".join(
        f"{field} = EXCLUDED.{field}" for field in fields if field != key
    )
    assignments += ", source_batch_id = EXCLUDED.source_batch_id, ingested_at = NOW()"
    return (
        f"INSERT INTO raw.{table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT ({key}) DO UPDATE SET {assignments}"
    )


def ingest_batch(validated_dir: Path, batch_id: int) -> dict[str, int]:
    """Upsert accepted CSV rows atomically; failed loads roll back all four tables."""
    if batch_id < 1:
        raise ValueError("batch_id must be a positive integer")
    if not validated_dir.is_dir():
        raise FileNotFoundError(f"Validated batch directory does not exist: {validated_dir}")

    schema_file = PROJECT_ROOT / "sql" / "01_raw_schema.sql"
    if not schema_file.is_file():
        raise FileNotFoundError(f"Raw schema definition is missing: {schema_file}")

    counts: dict[str, int] = {}
    with psycopg2.connect(**settings.database_kwargs()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_file.read_text(encoding="utf-8"))
            for table, (fields, key) in UPSERTS.items():
                rows = _read_rows(validated_dir / f"{table}.csv", fields)
                if rows:
                    values = [row + (batch_id,) for row in rows]
                    execute_values(
                        cursor,
                        _upsert_sql(table, fields, key),
                        values,
                        page_size=500,
                    )
                counts[table] = len(rows)
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", type=int, default=1)
    parser.add_argument("--input-dir", type=Path)
    args = parser.parse_args()
    input_dir = args.input_dir or settings.data_dir / "validated" / f"batch_{args.batch_id:08d}"
    print(ingest_batch(input_dir, args.batch_id))


if __name__ == "__main__":
    main()
