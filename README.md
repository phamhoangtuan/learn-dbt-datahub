# Plan: End-to-End Data Engineering Learning Pipeline

## Objective
Build a complete data pipeline using **DataHub**, **dbt**, and **Snowflake Emulator** to process simulated banking data. The project will implement **Medallion Architecture** and **Clean Architecture** principles, structured around the **DAMA-DMBOK** framework.

## Tech Stack
- **Source**: Python script simulating Stream/Micro-batch events (JSONL).
- **Storage/Compute**: `snowflake-emulator` (Go + DuckDB) to mimic Snowflake.
- **Transformation**: `dbt-snowflake` (or compatible adapter).
- **Governance**: DataHub (Metadata, Lineage).
- **Orchestration**: Makefiles / Shell Scripts.

## Phases

### Phase 1: Environment & Foundation (DAMA: Data Infrastructure) ✅
**Goal**: Set up the local development environment.
- [x] **Project Structure**: Created `ingestion/`, `dbt_project/`, `infrastructure/`, `scripts/`, `data/`, `tests/`.
- [x] **Snowflake Emulator**: Running via Docker on `localhost:8080` (`ghcr.io/nnnkkk7/snowflake-emulator`).
    - Proxy sidecar (`infrastructure/snowflake_proxy.py`) bridges connector 3.x ↔ emulator (gzip decompression + parameter type fixes).
- [x] **DataHub**: Available via `make datahub-up` (`datahub docker quickstart`, UI at `localhost:9002`).
- [x] **Python Env**: `uv` + Python 3.10, packages: `dbt-snowflake 1.9.4`, `faker`, `acryl-datahub`, `polars`, `duckdb`.
- [x] **dbt connection verified**: `make dbt-debug` → All checks passed.

### Phase 2: Data Generation & Ingestion (DAMA: Data Integration) ✅
**Goal**: Simulate a banking system generating "stream" data.
- [x] **Generator Script**: `scripts/generate_events.py` (`ingestion/generator.py`).
    - **Entities**: Accounts (Creation, Updates), Transactions (Credit, Debit, Transfer).
    - **Format**: JSONL (Newline Delimited JSON) to simulate stream logs.
    - **Output**: Writes to `data/landing_zone/` (62 account events + 200 transaction events).
- [x] **Ingestion Logic**: `scripts/load_to_emulator.py` (`ingestion/loader.py`).
    - Loads JSONL → `ACCOUNTS_RAW` (TEXT column) and `TRANSACTIONS_RAW` (TEXT column) via `INSERT INTO ... VALUES (...)`.
    - Emulator note: uses `TEXT` instead of `VARIANT` (DuckDB-backed); no `PARSE_JSON` / `COMMIT` support.
- [x] **Unit tests**: 12 tests in `tests/` (all green).

### Phase 3: Architecture & Modeling (DAMA: Data Architecture & Modeling) ✅
**Goal**: Define the architectural layers and business logic.
- [x] **Clean Architecture Design**:
    - **Entities (Inner Layer)**: `is_suspicious_transaction(amount, status)` macro — pure business rule (amount > 10000 AND status = 'COMPLETED').
    - **Use Cases (Middle Layer)**: Silver dbt models execute transformations (parse JSON, cast types, deduplicate).
    - **Adapters (Outer Layer)**: Bronze models normalize raw TEXT JSON in; Gold models serve BI-ready aggregates out.
- [x] **Medallion Layers**:
    - **Bronze**: `bronze_accounts_raw`, `bronze_transactions_raw` — raw TEXT selects with escape-fix.
    - **Silver**: `silver_accounts_clean` (deduplicated by latest event), `silver_transactions_clean` (parsed + `is_suspicious` flag).
    - **Gold**: `gold_daily_balance_snapshot` (latest balance per account per day), `gold_transaction_summary` (daily aggregates per account).
- [x] **dbt Tests**: 34 schema tests (not_null, unique, accepted_values) — all green.
- [x] **Proxy fixes**: Emulator comment-stripping (DuckDB rejects SQL prefixed with `/* */` comments); NUMBER→fixed type normalization for `count(*)` results.

### Phase 4: Implementation (DAMA: Data Quality & Interoperability) ✅
**Goal**: Write the dbt code and pipelines.
- [x] **dbt Project Setup**: `dbt init` (Phase 1), profiles.yml checked in.
- [x] **Bronze Layer**: Models select from raw tables with JSON escape correction.
- [x] **Silver Layer**: DuckDB `->>'field'` JSON extraction, type-casting, deduplication via `ROW_NUMBER()`.
- [x] **Gold Layer**: `DATE_TRUNC('day', ...)` aggregations for daily snapshots and transaction summaries.
- [x] **Testing**: 34 `dbt` tests (unique, not_null, accepted_values) — `dbt build` PASS=40 WARN=0 ERROR=0.

### Phase 5: Governance & Metadata (DAMA: Data Governance) ✅
**Goal**: Make the data discoverable and trustworthy.
- [x] **DataHub Ingestion**: `infrastructure/datahub_dbt_ingestion.yml` — `dbt-core` source recipe ingests models, lineage, and test results.
- [x] **Lineage**: DataHub shows Source → Bronze → Silver → Gold via column-level lineage from dbt manifest.
- [x] **Documentation**: `dbt docs generate` syncs `schema.yml` descriptions (column docs, test assertions) to DataHub.

### Phase 6: Orchestration (DAMA: Data Operations) ✅
**Goal**: Automate the flow.
- [x] **Makefile**: `make run` (pipeline) and `make run-full` (pipeline + governance) commands:
    1.  Generates new batch of data.
    2.  Loads data to Emulator.
    3.  Runs `dbt build`.
    4.  Ingests metadata to DataHub.

## Quick Start

### Run the full pipeline (Phase 2–4, emulator must be running)
```bash
make infra-up    # Start Snowflake Emulator on port 8080
make run         # generate → load → transform
```

### Run everything including governance (Phase 5–6, manages services automatically)
```bash
make run-full    # ~90s total: emulator up → pipeline → emulator down → DataHub up → metadata ingest
# Then open http://localhost:9002 to explore lineage
```

> **Port conflict note**: The Snowflake Emulator proxy and DataHub GMS both bind to port 8080.
> `make run-full` handles this automatically. Do **not** run `make infra-up` and `make datahub-up` simultaneously.

## Verification
- Verify `snowflake-emulator` accepts standard Snowflake SQL generated by dbt: `make dbt-debug`
- Verify DataHub correctly displays the dbt lineage: `make run-full`, then search for `medallion_pipeline` at `http://localhost:9002`.
