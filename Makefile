.DEFAULT_GOAL := help

.PHONY: help setup sync infra-up infra-down infra-logs dbt-debug datahub-up datahub-down datahub-ingest generate load transform run run-full

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*##"}; {printf "  %-16s %s\n", $$1, $$2}'

# ── Environment ──────────────────────────────────────────────────────────────

setup: sync infra-up  ## Full Phase 1 environment setup (deps + Snowflake Emulator)

sync:  ## Install Python dependencies via uv
	uv sync

# ── Snowflake Emulator ────────────────────────────────────────────────────────

infra-up:  ## Start Snowflake Emulator (DuckDB-backed, localhost:8082)
	docker compose -f infrastructure/docker-compose.yml up -d

infra-down:  ## Stop Snowflake Emulator
	docker compose -f infrastructure/docker-compose.yml down

infra-logs:  ## Tail Snowflake Emulator logs
	docker compose -f infrastructure/docker-compose.yml logs -f

# ── DataHub ───────────────────────────────────────────────────────────────────

datahub-up:  ## Start DataHub via acryl-datahub quickstart (UI at localhost:9002)
	DOCKER_HOST=unix://$(HOME)/.rd/docker.sock uv run datahub docker quickstart

datahub-down:  ## Stop DataHub
	DOCKER_HOST=unix://$(HOME)/.rd/docker.sock uv run datahub docker quickstart --stop

# ── dbt ───────────────────────────────────────────────────────────────────────

dbt-debug:  ## Verify dbt → Snowflake Emulator connection
	cd dbt_project && uv run dbt debug --profiles-dir .

# ── Pipeline (Phase 2+) ───────────────────────────────────────────────────────

generate:  ## Generate synthetic banking events (Phase 2)
	PYTHONPATH=. uv run python scripts/generate_events.py

load:  ## Load events into Snowflake Emulator Bronze layer (Phase 2)
	PYTHONPATH=. uv run python scripts/load_to_emulator.py

transform:  ## Run dbt models (Phase 4)
	cd dbt_project && uv run dbt build --profiles-dir .

# ── Governance ────────────────────────────────────────────────────────────────

datahub-ingest:  ## Ingest dbt metadata into DataHub (requires: make datahub-up)
	DOCKER_HOST=unix://$(HOME)/.rd/docker.sock uv run datahub ingest -c infrastructure/datahub_dbt_ingestion.yml

# ── Orchestration ─────────────────────────────────────────────────────────────

run:  ## Run full data pipeline: generate → load → transform (requires: make infra-up)
	$(MAKE) generate
	$(MAKE) load
	$(MAKE) transform

run-full:  ## Full pipeline + governance (requires: make infra-up + make datahub-up)
	$(MAKE) run
	$(MAKE) datahub-ingest
	@echo "Done. Open http://localhost:9002 to explore lineage."
