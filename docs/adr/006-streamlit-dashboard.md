# ADR 006: Streamlit dashboard for the MVP

- Status: accepted
- Date: 2026-07-29

## Context

The demo needs an executive interface without operating a separate BI server.

## Decision

Streamlit calls governed FastAPI endpoints and caches aggregate responses for a
short period. It never connects directly to raw or core employee tables.

## Consequences

The demo is self-contained and easy to run. Streamlit is not a replacement for
enterprise semantic-layer authorization or high-concurrency BI.

