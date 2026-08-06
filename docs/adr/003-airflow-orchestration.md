# ADR 003: Airflow orchestrates pipelines

- Status: accepted
- Date: 2026-07-29

## Context

Recurring, retryable, backfillable ingestion and transformation require durable
state and task-level observability.

## Decision

Airflow TaskFlow DAGs separate ingestion, transformation, quality, and the
end-to-end trigger chain. Database-heavy tasks use a pool; retries use
exponential backoff; one active run prevents overlapping publication.

## Consequences

Operators gain a familiar UI and recovery model at the cost of several local
services. `catchup=False` avoids accidental historical floods; deliberate
backfills use explicit CLI date ranges.

