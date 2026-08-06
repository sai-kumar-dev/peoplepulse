.PHONY: setup generate-data ingest dbt-deps dbt-run dbt-test quality airflow-up api-up dashboard-up demo test lint format typecheck ci clean down

COMPOSE := docker compose
PYTHON := python

setup:
	$(COMPOSE) build api dashboard airflow-init
	$(COMPOSE) up -d source-db warehouse airflow-db

generate-data:
	$(COMPOSE) run --rm api python -m data_generator.generate --employees 1000 --months 24 --seed 42 --output-dir /opt/peoplepulse/data/generated

ingest:
	$(COMPOSE) run --rm api python -m ingestion.cli load --input-dir /opt/peoplepulse/data/generated

dbt-deps:
	$(COMPOSE) run --rm dbt deps

dbt-run:
	$(COMPOSE) run --rm dbt build --target local

dbt-test:
	$(COMPOSE) run --rm dbt test --target local

quality:
	$(COMPOSE) run --rm api python -m peoplepulse.quality.cli

airflow-up:
	$(COMPOSE) up -d airflow-init airflow-webserver airflow-scheduler airflow-triggerer

api-up:
	$(COMPOSE) up -d api

dashboard-up:
	$(COMPOSE) up -d dashboard

demo:
	$(COMPOSE) up -d source-db warehouse airflow-db
	$(MAKE) generate-data
	$(MAKE) ingest
	$(COMPOSE) run --rm api python -m data_generator.generate --employees 1 --months 12 --seed 1337 --scenario deliberate_bad_record --output-dir /opt/peoplepulse/data/generated/deliberate_bad
	$(COMPOSE) run --rm api python -m ingestion.cli load --input-dir /opt/peoplepulse/data/generated/deliberate_bad
	$(MAKE) dbt-run
	$(MAKE) quality
	$(COMPOSE) up -d api dashboard airflow-init airflow-webserver airflow-scheduler airflow-triggerer
	@$(PYTHON) scripts/demo_urls.py

test:
	$(COMPOSE) run --rm test

lint:
	$(COMPOSE) run --rm test ruff check .

format:
	$(COMPOSE) run --rm test ruff format .

typecheck:
	$(COMPOSE) run --rm test mypy .

ci:
	$(COMPOSE) run --rm test sh -c "ruff format --check . && ruff check . && mypy . && pytest"
	$(COMPOSE) run --rm dbt deps
	$(COMPOSE) run --rm dbt parse --target local
	$(COMPOSE) config --quiet

down:
	$(COMPOSE) down

clean:
	$(COMPOSE) down --remove-orphans
	@$(PYTHON) scripts/clean.py
