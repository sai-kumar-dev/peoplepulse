# ADR 004: Dimensional warehouse model

- Status: accepted
- Date: 2026-07-29

## Context

Workforce metrics need consistent department, employee, and date semantics with
fast aggregate queries.

## Decision

Core uses conformed dimensions and atomic lifecycle facts. Marts declare a
business grain and pre-aggregate common executive views. Technical audit data
stays separate from business facts.

## Consequences

Queries are understandable and dashboard-friendly. Some denormalization and
storage duplication are intentional, and metric definitions must be governed.

