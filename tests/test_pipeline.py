import csv
import json

from ingestion.generate_data import generate_batch
from ingestion.validation import validate_batch


def test_generation_is_deterministic_for_a_batch(tmp_path):
    first = generate_batch(7, tmp_path / "first", customer_count=6, product_count=4, order_count=8)
    second = generate_batch(7, tmp_path / "second", customer_count=6, product_count=4, order_count=8)

    for filename in ("customers.csv", "products.csv", "orders.csv", "order_items.csv"):
        assert (first / filename).read_bytes() == (second / filename).read_bytes()


def test_generation_supports_calendar_shaped_batch_ids(tmp_path):
    batch = generate_batch(
        20261125,
        tmp_path / "raw",
        customer_count=4,
        product_count=3,
        order_count=3,
    )

    with (batch / "orders.csv").open(newline="", encoding="utf-8") as orders:
        order_dates = [row["order_date"] for row in csv.DictReader(orders)]
    assert order_dates[-1] == "not-a-date"
    assert all(
        value.startswith(("2025-", "2026-", "2027-"))
        for value in order_dates[:-1]
    )


def test_validation_rejects_bad_rows_and_downstream_orphans(tmp_path):
    source = generate_batch(2, tmp_path / "raw", customer_count=6, product_count=4, order_count=8)
    output = tmp_path / "validated" / "batch_00000002"

    report = validate_batch(source, output)

    assert report["totals"]["rejected_rows"] >= 5
    assert report["tables"]["customers"]["rejection_reasons"]["email must be a valid non-empty address"] == 1
    assert any("duplicate customer_id" in reason for reason in report["tables"]["customers"]["rejection_reasons"])
    assert report["tables"]["orders"]["rejection_reasons"]["order_date must be an ISO datetime"] == 1
    assert any("does not reference an accepted customer" in reason for reason in report["tables"]["orders"]["rejection_reasons"])
    assert any("does not reference an accepted product" in reason for reason in report["tables"]["order_items"]["rejection_reasons"])
    assert report["tables"]["order_items"]["rejection_reasons"]["quantity must be a positive integer"] == 1
    assert (output / "rejected_records.jsonl").is_file()
    assert json.loads((output / "quality_report.json").read_text(encoding="utf-8"))["totals"] == report["totals"]

    with (output / "orders.csv").open(newline="", encoding="utf-8") as accepted_orders:
        accepted_ids = {row["order_id"] for row in csv.DictReader(accepted_orders)}
    with (output / "order_items.csv").open(newline="", encoding="utf-8") as accepted_items:
        assert all(row["order_id"] in accepted_ids for row in csv.DictReader(accepted_items))


def test_validation_fails_for_missing_batch(tmp_path):
    try:
        validate_batch(tmp_path / "missing", tmp_path / "validated")
    except FileNotFoundError as error:
        assert "Batch directory does not exist" in str(error)
    else:
        raise AssertionError("Expected missing batch input to fail explicitly")
