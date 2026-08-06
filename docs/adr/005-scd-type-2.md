# ADR 005: SCD Type 2 employee history

- Status: accepted
- Date: 2026-07-29

## Context

Department, manager, job, level, location, and status changes must be queryable
as of a past business date.

## Decision

`dim_employee` uses a surrogate key, business key, `valid_from`, exclusive
`valid_to`, `is_current`, record hash, source, and load timestamp. A changed hash
opens a new version and closes the previous version. Tests enforce one current
row and non-overlapping ranges.

## Consequences

Historical metrics remain reproducible. Late events require ordered effective
dates and may rebuild a business key's timeline rather than append blindly.

