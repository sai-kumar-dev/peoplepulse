# Initial assessment and assumptions

Assessment date: 2026-07-29.

- The supplied workspace was empty and was not a Git repository. There was no
  existing implementation, CI configuration, or test suite to preserve.
- The host has Python 3.13, while the required runtime is Python 3.12. Canonical
  execution therefore uses Python 3.12 container images.
- Docker CLI and Compose are installed. Image pulls and builds still depend on a
  reachable container engine and registry.
- No Snowflake credentials were supplied. The Snowflake adapter is configuration
  and deployment SQL only; local PostgreSQL remains mandatory and authoritative.
- Every generated identity is fictional. Synthetic records are still handled as
  if restricted so the architecture demonstrates real controls.
- The first implementation milestone is the brief's named vertical slice:
  employees, departments, hire/termination events, raw ingestion, employee SCD2,
  core facts/marts, Airflow, API, dashboard, and end-to-end verification.
- Additional workforce domains can reuse the connector, quality, repository,
  and dimensional-model boundaries without widening raw-schema access.

