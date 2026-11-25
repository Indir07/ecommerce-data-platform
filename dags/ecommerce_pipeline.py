"""Daily, rerunnable orchestration for the local e-commerce ELT platform."""

from __future__ import annotations

import json
import logging
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow.decorators import dag, task

from ingestion.config import PROJECT_ROOT, settings
from ingestion.generate_data import generate_batch
from ingestion.load_data import ingest_batch
from ingestion.validation import validate_batch

logger = logging.getLogger(__name__)
DBT_PROJECT_DIR = PROJECT_ROOT / "dbt_project"
DBT_EXECUTABLE = os.getenv("DBT_EXECUTABLE", "dbt")


@dag(
    dag_id="ecommerce_incremental_elt",
    description="Generate, validate, load, transform, and test e-commerce batches.",
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "data-platform", "retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["ecommerce", "elt", "local"],
)
def ecommerce_incremental_elt():
    @task
    def generate_source_batch(**context) -> int:
        dag_run = context.get("dag_run")
        run_config = (dag_run.conf or {}) if dag_run else {}
        default_batch_id = context["data_interval_start"].strftime("%Y%m%d")
        batch_id = int(run_config.get("batch_id", default_batch_id))
        batch_dir = generate_batch(batch_id, settings.data_dir / "raw")
        logger.info("Generated batch %s at %s", batch_id, batch_dir)
        return batch_id

    @task
    def validate_source_batch(batch_id: int) -> str:
        source_dir = settings.data_dir / "raw" / f"batch_{batch_id:08d}"
        validated_dir = settings.data_dir / "validated" / f"batch_{batch_id:08d}"
        report = validate_batch(source_dir, validated_dir)
        logger.info("Batch %s quality metrics: %s", batch_id, json.dumps(report["totals"], sort_keys=True))
        return str(validated_dir)

    @task
    def load_raw_batch(validated_dir: str, batch_id: int) -> None:
        counts = ingest_batch(Path(validated_dir), batch_id)
        logger.info("Loaded batch %s into raw tables: %s", batch_id, counts)

    @task
    def transform_warehouse() -> None:
        subprocess.run(
            [DBT_EXECUTABLE, "run", "--project-dir", str(DBT_PROJECT_DIR), "--profiles-dir", str(DBT_PROJECT_DIR)],
            cwd=DBT_PROJECT_DIR,
            env=os.environ.copy(),
            check=True,
        )

    @task
    def test_warehouse() -> None:
        subprocess.run(
            [DBT_EXECUTABLE, "test", "--project-dir", str(DBT_PROJECT_DIR), "--profiles-dir", str(DBT_PROJECT_DIR)],
            cwd=DBT_PROJECT_DIR,
            env=os.environ.copy(),
            check=True,
        )

    batch = generate_source_batch()
    validated = validate_source_batch(batch)
    loaded = load_raw_batch(validated, batch)
    transformed = transform_warehouse()
    tested = test_warehouse()
    loaded >> transformed
    transformed >> tested


ecommerce_incremental_elt()
