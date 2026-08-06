# PeoplePulse interview guide

## Two-minute architecture explanation

PeoplePulse simulates several HR source contracts but delivers a complete
employee lifecycle vertical slice. A Python connector layer extracts CSV, JSON,
PostgreSQL, or REST records, validates schema and business keys, hashes rows,
deduplicates repeated batches, and writes raw PostgreSQL tables plus batch and
dead-letter metadata. Airflow coordinates this boundary but contains no business
SQL.

dbt transforms raw rows through staging and reusable intermediate models into an
SCD Type 2 employee dimension, lifecycle facts, monthly snapshots, and aggregate
marts. Critical dbt and Python quality checks block publication. FastAPI exposes
only aggregate metrics; Streamlit consumes that API. Local PostgreSQL makes the
demo free, while an isolated Snowflake adapter maps the same controls to roles,
masking policies, resource monitors, and warehouses.

## Why SCD Type 2?

Headcount and attrition need the employee's department, manager, job, level,
location, and status as they were on an earlier date. Overwriting the current row
would restate history. The tracked-attribute hash detects a change, closes the
old half-open range, and inserts a new version. Surrogate keys let facts bind to
the effective version. Tests enforce exactly one current row and no overlaps.

Late-arriving changes are the hard case: append-only merge is insufficient if an
event belongs between existing versions. The safe approach is to rebuild that
business key's ordered timeline transactionally, then repair affected fact keys.

## Incremental and idempotent loading

A source connector returns records plus a candidate checkpoint. Validation
separates accepted and rejected rows. A canonical row hash/business event key
prevents duplicate raw inserts across repeated batches. Counts reconcile as:

```text
extracted = loaded + rejected + duplicate
```

Only after the load and audit rows commit does the checkpoint advance. A retry
therefore converges on the same state instead of skipping or doubling records.

## Quality strategy

There are three layers:

1. Contract checks at ingestion: fields, types, enumeration, schema drift.
2. Warehouse tests: keys, relationships, employment dates, SCD range
   consistency, and metric business rules.
3. Operational checks: freshness, volume, duplicate/reject rates, reconciliation.

Critical failures persist evidence and stop publication. Warnings remain visible
without stopping the pipeline. Thresholds are configuration, not silent code
constants.

## Airflow reliability

Separate DAGs keep ingestion, dbt, and quality independently retryable. The
end-to-end DAG triggers them sequentially and waits. Tasks are idempotent, use
logical dates, retry infrastructure failures with exponential backoff, allow one
active publication run, and put database-heavy work in a pool. `catchup=False`
prevents an accidental backlog; an operator invokes bounded backfills explicitly.

## Governance and PII

Synthetic data is governed as if real. Analysts do not receive raw access.
Names, contact fields, birth dates, employee identifiers, and pay are centrally
classified and masked. APIs return aggregates, error details are safe, logs omit
payloads, and sensitive access decisions have an audit event. Local bearer tokens
demonstrate role policy only; production would use an IdP and purpose-aware
claims.

## Snowflake cost strategy

Use isolated X-Small loading, transforming, and reporting warehouses with
auto-resume and 60–120 second auto-suspend. A resource monitor notifies at 75%,
suspends at 90%, and hard-suspends at quota. Date predicates support partition
pruning; query tags attribute cost. Resize only from queue/spill evidence, avoid
routine full refreshes, use result caching and aggregate marts, and use zero-copy
clones for development.

## Trade-offs and limitations

- PostgreSQL and Snowflake do not have identical merge, policy, or performance
  semantics; both targets need production qualification.
- Streamlit is ideal for a portfolio MVP, not a highly concurrent enterprise BI
  platform.
- Synthetic distributions demonstrate pipelines, not fairness or causal
  workforce analysis.
- The initial vertical slice prioritizes employee lifecycle metrics. Recruitment,
  compensation, learning, and performance endpoints can expose honest
  unavailable/demo states until their full facts are loaded.
- Local role tokens and static policy mappings must be replaced by enterprise
  identity and a policy service in production.

## Scaling answer

Partition extraction by source watermark and entity; stream large files in
batches; bulk-load raw data; parallelize independent entities under source and
warehouse limits; keep facts incremental; pre-aggregate common mart grains; add
indexes or clustering only from profiles; cache stable API aggregates; isolate
compute workloads; and archive raw batches under retention policy. For very high
event volume, object storage plus a managed ingestion service can replace direct
database writes without changing downstream contracts.

