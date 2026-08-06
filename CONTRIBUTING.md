# Contributing

Use Python 3.12 and make focused changes. Copy `.env.example` to `.env`; never
commit it.

Before opening a pull request:

```bash
ruff format --check .
ruff check .
mypy .
pytest
cd dbt
dbt deps
dbt parse --target local
dbt build --target local
cd ..
docker compose config --quiet
```

New source fields require a versioned connector contract, raw DDL, staging
mapping, classification/retention decision, tests, and data-dictionary update.
New metrics must declare grain, denominator, owner, refresh frequency,
sensitivity, and edge-case behavior.

Do not place transformation SQL in routes or DAGs. Keep domain logic in services,
warehouse transformations in dbt, and orchestration in Airflow.

