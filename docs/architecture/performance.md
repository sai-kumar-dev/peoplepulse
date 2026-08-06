# Cost and performance strategy

The laptop-friendly default is 1,000 employees and 24 months. The benchmark
command supports 10,000 employees; million-row validation is opt-in because
hardware differs.

## PostgreSQL

- Raw access paths index `(updated_at, employee_id)` and event dates with their
  common department filter.
- Aggregate endpoints read marts instead of joining employee-grain facts per
  request, preventing N+1 behavior.
- Bind parameters and allow-listed sort/filter fields are required. The API
  applies connection pooling and statement timeouts.
- Use `EXPLAIN (ANALYZE, BUFFERS)` against representative production-like
  volumes before adding indexes. Each extra index increases raw-load cost.

## dbt

- Staging isolates type cleanup and deterministic deduplication.
- Employee history and event facts use stable hashes/keys so repeated batches
  converge.
- Incremental predicates should use `_ingested_at` for load deltas and
  business-effective dates for downstream pruning.
- Snapshot-like aggregates are precomputed by month and dimensions used by the
  dashboard. Full refresh is a recovery operation, not a daily default.

## Snowflake

- Loading, transformation, and reporting workloads have separate `XSMALL`
  warehouses with 60–120 second auto-suspend.
- The resource monitor warns at 75%, suspends at 90%, and hard-suspends at 100%
  of the configured quota.
- Filter large facts by effective/snapshot date so micro-partition pruning can
  work; introduce clustering only after query-profile evidence.
- Use result caching for repeated dashboards, query tags for attribution,
  zero-copy clones for development, and Time Travel for short recovery windows.

Run:

```bash
python scripts/benchmark.py --employees 10000 --months 36
python scripts/benchmark.py --employees 10000 --api-url http://localhost:8000/api/v1/workforce/summary
```

The report includes row counts, generator duration, peak Python allocation, and
optional API p50/p95 latency. Transformation timing is available in Airflow and
dbt `run_results.json`.

