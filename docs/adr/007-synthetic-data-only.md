# ADR 007: Synthetic data only

- Status: accepted
- Date: 2026-07-29

## Context

Real employee data would create unacceptable privacy, consent, and retention
obligations for a portfolio project.

## Decision

All identities and lifecycle events are deterministically generated. Test
scenarios intentionally include invalid records. The platform nevertheless
classifies and protects synthetic PII exactly as production data.

## Consequences

The repository is safe to share and tests are reproducible. Synthetic
distributions cannot validate every real-world bias, regulation, or HR process.

