#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

docker compose up -d source-db warehouse airflow-db
docker compose run --rm api python -m data_generator.generate \
  --employees 1000 --months 24 --seed 42 --scenario normal \
  --output-dir /opt/peoplepulse/data/generated
docker compose run --rm api python -m ingestion.cli load \
  --input-dir /opt/peoplepulse/data/generated

docker compose run --rm api python -m data_generator.generate \
  --employees 1 --months 12 --seed 1337 --scenario deliberate_bad_record \
  --output-dir /opt/peoplepulse/data/generated/deliberate_bad
docker compose run --rm api python -m ingestion.cli load \
  --input-dir /opt/peoplepulse/data/generated/deliberate_bad

docker compose run --rm dbt deps
docker compose run --rm dbt build --target local
docker compose run --rm api python -m peoplepulse.quality.cli
docker compose up -d \
  airflow-init airflow-webserver airflow-scheduler airflow-triggerer api dashboard
python scripts/demo_urls.py

