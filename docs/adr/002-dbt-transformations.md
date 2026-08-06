# ADR 002: dbt owns warehouse transformations

- Status: accepted
- Date: 2026-07-29

## Context

Transformation logic needs lineage, documentation, tests, and reviewable SQL.

## Decision

Python preserves and validates raw batches; dbt owns staging normalization,
business transformations, dimensional models, facts, and marts. DAG files only
orchestrate dbt selectors and do not duplicate metric formulas.

## Consequences

Lineage and tests are visible in dbt artifacts, and analysts can review SQL.
Cross-database differences must remain in macros or target-specific
configuration.

