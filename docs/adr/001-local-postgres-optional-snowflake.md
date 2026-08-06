# ADR 001: PostgreSQL locally, Snowflake as an adapter

- Status: accepted
- Date: 2026-07-29

## Context

The portfolio must run without paid infrastructure but also demonstrate a
credible Snowflake deployment.

## Decision

PostgreSQL 16 is the source simulator and local analytics warehouse. Warehouse
access is isolated behind loader/repository configuration and dbt targets.
Snowflake-specific roles, policies, warehouses, and cost controls live under
`infrastructure/snowflake` and are never required by local CI.

## Consequences

The project is reproducible on a laptop and SQL stays mostly portable. A few
incremental and security features need adapter-specific implementations, so both
targets require separate production qualification.

