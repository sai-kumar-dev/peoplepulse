# ADR 008: Role-based PII restrictions

- Status: accepted
- Date: 2026-07-29

## Context

Analytics consumers need aggregates, while a small restricted group may require
employee-level operational access.

## Decision

Raw schemas are loader/transformer-only. The API exposes aggregate marts and
admin operations require a role-bearing local token. A central field policy
masks names, contact data, birth dates, identifiers, and pay. Snowflake maps the
same intent to roles, tags, masking policies, and secure views.

## Consequences

Least privilege is explicit and testable. The local bearer-token mechanism is
for demonstration only; production must use an identity provider, short-lived
tokens, purpose claims, and centralized audit retention.

