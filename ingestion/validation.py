"""Validate CSV batches and persist accepted rows, rejects, and quality metrics."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ingestion.generate_data import (
    CUSTOMER_FIELDS,
    ORDER_FIELDS,
    ORDER_ITEM_FIELDS,
    PRODUCT_FIELDS,
)

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ORDER_STATUSES = {"cancelled", "delivered", "pending", "processing", "shipped"}
PRODUCT_CATEGORIES = {"apparel", "beauty", "electronics", "home", "sports"}
TABLE_FIELDS = {
    "customers": CUSTOMER_FIELDS,
    "products": PRODUCT_FIELDS,
    "orders": ORDER_FIELDS,
    "order_items": ORDER_ITEM_FIELDS,
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def _parse_positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise ValueError("must be greater than zero")
    return parsed


def _parse_positive_decimal(value: str) -> Decimal:
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("must be a finite value greater than zero")
    return parsed


def _parse_nonnegative_decimal(value: str) -> Decimal:
    parsed = Decimal(value)
    if not parsed.is_finite() or parsed < 0:
        raise ValueError("must be a finite non-negative value")
    return parsed


def _validate_records(
    table: str,
    rows: list[dict[str, str]],
    related_ids: dict[str, set[int]],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    accepted: list[dict[str, str]] = []
    rejected: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    id_field = {
        "customers": "customer_id",
        "products": "product_id",
        "orders": "order_id",
        "order_items": "order_item_id",
    }[table]

    for row_number, row in enumerate(rows, start=2):
        reasons: list[str] = []
        record_id: int | None = None
        try:
            record_id = _parse_positive_int(row.get(id_field, ""))
        except (TypeError, ValueError):
            reasons.append(f"{id_field} must be a positive integer")

        if record_id is not None:
            if record_id in seen_ids:
                reasons.append(f"duplicate {id_field}: {record_id}")
            else:
                seen_ids.add(record_id)

        if table == "customers":
            for field in ("first_name", "last_name", "city"):
                if not row.get(field, "").strip():
                    reasons.append(f"{field} is required")
            if not EMAIL_PATTERN.fullmatch(row.get("email", "")):
                reasons.append("email must be a valid non-empty address")
            try:
                date.fromisoformat(row.get("signup_date", ""))
            except ValueError:
                reasons.append("signup_date must be an ISO date")
        elif table == "products":
            for field in ("product_name", "brand"):
                if not row.get(field, "").strip():
                    reasons.append(f"{field} is required")
            if row.get("category") not in PRODUCT_CATEGORIES:
                reasons.append("category is not an accepted product category")
            try:
                _parse_positive_decimal(row.get("unit_price", ""))
            except (InvalidOperation, ValueError):
                reasons.append("unit_price must be a finite value greater than zero")
        elif table == "orders":
            try:
                customer_id = _parse_positive_int(row.get("customer_id", ""))
                if customer_id not in related_ids["customers"]:
                    reasons.append(f"customer_id {customer_id} does not reference an accepted customer")
            except (TypeError, ValueError):
                reasons.append("customer_id must be a positive integer")
            try:
                datetime.fromisoformat(row.get("order_date", ""))
            except ValueError:
                reasons.append("order_date must be an ISO datetime")
            if row.get("status") not in ORDER_STATUSES:
                reasons.append("status is not an accepted order status")
            try:
                _parse_nonnegative_decimal(row.get("total_amount", ""))
            except (InvalidOperation, ValueError):
                reasons.append("total_amount must be a finite non-negative value")
        else:
            try:
                order_id = _parse_positive_int(row.get("order_id", ""))
                if order_id not in related_ids["orders"]:
                    reasons.append(f"order_id {order_id} does not reference an accepted order")
            except (TypeError, ValueError):
                reasons.append("order_id must be a positive integer")
            try:
                product_id = _parse_positive_int(row.get("product_id", ""))
                if product_id not in related_ids["products"]:
                    reasons.append(f"product_id {product_id} does not reference an accepted product")
            except (TypeError, ValueError):
                reasons.append("product_id must be a positive integer")
            try:
                _parse_positive_int(row.get("quantity", ""))
            except (TypeError, ValueError):
                reasons.append("quantity must be a positive integer")
            try:
                _parse_positive_decimal(row.get("unit_price", ""))
            except (InvalidOperation, ValueError):
                reasons.append("unit_price must be a finite value greater than zero")

        if reasons:
            rejected.append({"table": table, "row_number": row_number, "reasons": reasons, "record": row})
        else:
            accepted.append(row)
            if record_id is not None:
                related_ids.setdefault(table, set()).add(record_id)
    return accepted, rejected


def validate_batch(batch_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Validate tables in dependency order; write accepted CSVs and JSON reports."""
    if not batch_dir.is_dir():
        raise FileNotFoundError(f"Batch directory does not exist: {batch_dir}")

    related_ids: dict[str, set[int]] = {
        "customers": set(),
        "products": set(),
        "orders": set(),
    }
    accepted_by_table: dict[str, list[dict[str, str]]] = {}
    rejected: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {"tables": {}}
    for table in ("customers", "products", "orders", "order_items"):
        rows = _read_csv(batch_dir / f"{table}.csv")
        accepted, table_rejected = _validate_records(table, rows, related_ids)
        accepted_by_table[table] = accepted
        rejected.extend(table_rejected)
        reason_counts = Counter(
            reason for item in table_rejected for reason in item["reasons"]
        )
        metrics["tables"][table] = {
            "input_rows": len(rows),
            "accepted_rows": len(accepted),
            "rejected_rows": len(table_rejected),
            "rejection_reasons": dict(sorted(reason_counts.items())),
        }

    if not any(accepted_by_table.values()):
        raise ValueError(f"No valid rows found in batch {batch_dir.name}")

    output_dir.mkdir(parents=True, exist_ok=True)
    for table, rows in accepted_by_table.items():
        path = output_dir / f"{table}.csv"
        with path.open("w", newline="", encoding="utf-8") as output:
            writer = csv.DictWriter(output, fieldnames=TABLE_FIELDS[table])
            writer.writeheader()
            writer.writerows(rows)

    total_input = sum(item["input_rows"] for item in metrics["tables"].values())
    total_accepted = sum(item["accepted_rows"] for item in metrics["tables"].values())
    total_rejected = sum(item["rejected_rows"] for item in metrics["tables"].values())
    metrics["batch"] = batch_dir.name
    metrics["totals"] = {
        "input_rows": total_input,
        "accepted_rows": total_accepted,
        "rejected_rows": total_rejected,
        "rejection_rate": round(total_rejected / total_input, 4) if total_input else 0.0,
    }

    with (output_dir / "rejected_records.jsonl").open("w", encoding="utf-8") as output:
        for item in rejected:
            output.write(json.dumps(item, sort_keys=True) + "\n")
    with (output_dir / "quality_report.json").open("w", encoding="utf-8") as output:
        json.dump(metrics, output, indent=2, sort_keys=True)
        output.write("\n")
    return metrics
