# E-Commerce Incremental ELT Data Platform

A local, end-to-end data engineering portfolio project. It generates reproducible e-commerce batches, validates and loads them into PostgreSQL, transforms them with dbt, and orchestrates the workflow with Apache Airflow.

## Business problem

An online retailer needs trustworthy customer, product, order, and order-line data for sales reporting. Source data can be late, repeated, incomplete, or malformed. This project demonstrates how to keep an auditable raw layer, reject bad records before they reach warehouse constraints, and incrementally publish tested analytics models.

## Architecture and data flow

```text
Deterministic Python batch generator
                 |
                 v
       data/raw/batch_<id>/*.csv
                 |
                 v
Python validation --> accepted CSVs + rejected_records.jsonl + quality_report.json
                 |
                 v
PostgreSQL raw schema (transactional primary-key upserts)
                 |
                 v
dbt staging views --> intermediate order-line view
                 |
                 v
analytics.dim_customers / analytics.dim_products / analytics.fact_orders
                 ^
                 |
      Airflow LocalExecutor DAG
```

PostgreSQL is the only database service. It holds both the `ecommerce` warehouse database and the separate `airflow` metadata database. Airflow uses LocalExecutor rather than Redis/Celery, keeping the local stack small. No cloud account, paid API, or external data service is required.

## Technology and learning map

| Component | Purpose | Engineering concept |
| --- | --- | --- |
| `ingestion/generate_data.py` | Produces a deterministic, repeatable batch with a few intentional defects. | Reproducible test data and batch identity |
| `ingestion/validation.py` | Checks required fields, IDs, dates, numeric values, allowed categories/statuses, and parent-child references. Writes accepted rows, a JSONL reject log, and machine-readable metrics. | Data contracts, quarantine, referential integrity |
| `ingestion/load_data.py` | Loads accepted CSVs in dependency order inside one PostgreSQL transaction. Primary-key conflicts update existing rows instead of duplicating them. | Atomicity and idempotent upserts |
| `sql/01_raw_schema.sql` | Creates constrained raw tables and access-path indexes. | Database constraints as a second line of defense |
| `dbt_project/models/staging/` | Gives raw columns consistent names and types and declares dbt sources. | Thin staging models and source freshness lineage |
| `dbt_project/models/intermediate/` | Computes reusable order-line amounts. | Shared transformation logic |
| `dbt_project/models/marts/` | Builds current customer/product dimensions and an order-grain fact table. | Dimensional modeling and incremental merge |
| `dags/ecommerce_pipeline.py` | Runs generation, validation, ingestion, dbt transformations, and dbt tests with retries. | Dependency-driven orchestration and recoverable tasks |
| `docker-compose.yml` | Starts PostgreSQL, initializes Airflow metadata, and runs its webserver and scheduler. | Reproducible local services and health checks |

## Repository layout

```text
.
├── dags/                     # Airflow orchestration DAG
├── data/                     # Local generated, accepted, and rejected batch files
├── dbt_project/
│   ├── models/
│   │   ├── staging/          # Raw sources and typed views
│   │   ├── intermediate/     # Reusable order-line calculations
│   │   └── marts/            # Incremental dimensions and order fact
│   ├── tests/                # Singular dbt quality tests
│   ├── dbt_project.yml
│   └── profiles.yml
├── ingestion/                # Generator, validators, configuration, PostgreSQL loader
├── logs/                     # Airflow task and scheduler logs
├── scripts/                  # Airflow initialization helpers
├── sql/                      # Database initialization and raw schema
├── tests/                    # Focused Python unit tests
├── docker-compose.yml
├── Dockerfile
├── requirements.txt          # Local Python tooling
└── requirements-airflow.txt  # Dependencies installed in the Airflow image
```

## Windows 11 setup

1. Install Docker Desktop and enable its WSL 2 engine. Start Docker Desktop before running Compose. A few GB of memory are sufficient for this PostgreSQL + LocalExecutor setup; more memory mainly helps the first Airflow image build.
2. Open this folder in VS Code. In PowerShell, create local settings from the example:

   ```powershell
   Copy-Item .env.example .env
   ```

   Change the local-only passwords in `.env` if desired. `.env` is ignored by Git. The supplied values are for a private local development stack only; do not expose the services to a network with those defaults.
3. Optional: create a local Python environment for running the generator, validator, and unit tests outside Docker:

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   python -m pytest -q
   ```

   If PowerShell blocks activation, use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe -m pytest -q` instead. The Airflow image contains dbt Core and its PostgreSQL adapter; local dbt installation is not needed.

## Start, run, and stop

Build the custom Airflow image and start the services:

```powershell
docker compose up --build -d
docker compose ps
```

Wait for `postgres`, `airflow-webserver`, and `airflow-scheduler` to report healthy. The first build downloads the pinned Airflow/dbt dependencies and can take several minutes. Airflow is at <http://localhost:8080>; sign in with `AIRFLOW_ADMIN_USERNAME` and `AIRFLOW_ADMIN_PASSWORD` from `.env` (defaults: `admin` / `admin`).

In the Airflow UI, unpause **`ecommerce_incremental_elt`** and trigger it. For a first run, supply `{"batch_id": 1}` in the trigger configuration. Trigger a later batch with `{"batch_id": 2}`. Re-triggering the same batch ID is safe and updates the same source keys. Alternatively, scheduled runs derive a positive batch ID from their interval start date.

The DAG tasks run in this order:

1. Generate deterministic CSV files under `data/raw/batch_<id>/`.
2. Validate into `data/validated/batch_<id>/`, logging rejects and metrics.
3. Transactionally upsert accepted rows into `raw`.
4. Run `dbt run` to update staging/intermediate models and merge mart rows.
5. Run `dbt test`; a failed transformation or test fails the Airflow run and is visible in task logs.

Stop containers without deleting data:

```powershell
docker compose down
```

Remove the PostgreSQL named volume only when you intentionally want to reset both databases:

```powershell
docker compose down --volumes
```

Generated files and Airflow logs are bind-mounted into this project folder and are not removed by `docker compose down`.

## Run stages manually

With the optional local Python dependencies installed and PostgreSQL running, the Python steps can also be run in PowerShell:

```powershell
python -m ingestion.generate_data --batch-id 1
python -m ingestion.validate_data --batch-id 1
python -m ingestion.load_data --batch-id 1
```

The dbt commands run in the Airflow image, which has the matching PostgreSQL hostname and credentials:

```powershell
docker compose exec airflow-webserver dbt run --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project
docker compose exec airflow-webserver dbt test --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project
```

## Incremental and rerun behavior

- The generator uses a fixed seed plus the requested batch ID. Re-generating one ID produces the same files, and IDs are separated between order batches.
- Customers and products have stable identifiers across batches, so a later batch exercises updates. Each order's IDs include its batch ID.
- The validator writes only accepted rows to the loader input. Duplicate IDs and malformed values are rejected with row-level reasons; rejected source CSVs are retained for audit.
- PostgreSQL `ON CONFLICT` upserts by primary key. All four tables load in foreign-key order in one transaction, so reruns do not duplicate records and partial loads roll back.
- dbt marts use incremental `merge` models keyed by their business IDs. The source `ingested_at` timestamp acts as a simple watermark; using `>=` includes rows from the latest load and makes a same-batch rerun safe. A full rebuild is available with `dbt run --full-refresh`.
- The incremental dimensions represent current attributes, not historical slowly changing dimension versions. See future improvements before using this pattern for audit-grade history.

## Database and data-quality contract

The `raw` schema contains `customers`, `products`, `orders`, and `order_items`. Primary keys, required columns, positive-value checks, accepted order statuses, foreign keys, and indexes protect the loaded layer. `source_batch_id` and `ingested_at` support lineage and incremental processing.

The generator intentionally introduces a duplicate customer ID, a blank email, a non-positive product price, an order with an invalid date and unknown customer, an item with an invalid product reference, and a zero-quantity item. The validator checks:

- Duplicate/non-positive IDs and required customer/product fields.
- Email format, ISO signup/order dates, and allowed categories/statuses.
- Positive prices/quantities and non-negative order totals.
- Order-to-customer, item-to-order, and item-to-product references.

Every batch's `quality_report.json` reports input, accepted, and rejected row counts and reason counts per table, plus an overall rejection rate. `rejected_records.jsonl` captures each rejected row and all detected reasons. Airflow logs the summary. dbt schema tests cover uniqueness, nullability, accepted values, and relationships; a singular test checks non-negative fact measures.

## Analytics models

| Model | Grain | Purpose |
| --- | --- | --- |
| `stg_customers`, `stg_products`, `stg_orders`, `stg_order_items` | One row per corresponding raw record | Typed, documented source boundary |
| `int_order_items` | One row per order line | Computes line amount |
| `dim_customers` | One row per current customer | Current customer attributes |
| `dim_products` | One row per current product | Current product attributes and price |
| `fact_orders` | One row per order | Order totals plus count and subtotal of accepted lines |

Warehouse tables are in the `analytics` schema of the `ecommerce` database. A source order total can differ from accepted line subtotals when a line is rejected; both measures remain available for reconciliation rather than silently dropping the source total.

## Tests and troubleshooting

Run Python unit tests:

```powershell
python -m pytest -q
```

Run dbt tests after at least one successful load:

```powershell
docker compose exec airflow-webserver dbt test --project-dir /opt/airflow/dbt_project --profiles-dir /opt/airflow/dbt_project
```

Useful diagnostics:

```powershell
docker compose ps
docker compose logs --tail 100 postgres
docker compose logs --tail 100 airflow-init
docker compose logs --tail 100 airflow-scheduler
```

If PostgreSQL is already using port 5432, set `POSTGRES_PORT` in `.env` to an available host port. Compose keeps the container-side port at 5432. If initialization fails, inspect the service logs before resetting anything; `docker compose down --volumes` permanently deletes the local database contents.

## Screenshots

Add portfolio screenshots here after running the project:

- Airflow DAG graph showing the task dependencies.
- A successful DAG run with all five stages green.
- dbt test results and the `analytics` schema in a PostgreSQL client.
- Example `quality_report.json` and rejected-record log.

## Future improvements

- Add snapshot-based slowly changing dimensions for customer and product history.
- Add source freshness SLAs, late-arriving data handling, and backfill controls.
- Add reconciliation tests for order totals and a documented refund/discount model.
- Publish dbt docs artifacts and add CI for Python tests, dbt parsing, and Compose validation.
- Add schema-versioned source contracts and configurable, measured quality thresholds.

## Security note

All data and credentials in this project are synthetic. Compose publishes PostgreSQL and Airflow ports to localhost for local development; change the defaults and restrict network access before any shared deployment. Do not commit `.env` or use the sample passwords outside a private local environment.
