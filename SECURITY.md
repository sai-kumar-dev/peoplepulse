# Security policy

PeoplePulse contains synthetic data only. Treat generated employee-level rows as
restricted anyway: do not post raw payloads, screenshots of identities, or local
environment files in an issue.

Report a suspected vulnerability privately to the repository maintainer. Include
the affected component, reproduction using synthetic data, impact, and a safe
mitigation. Do not include credentials or exploit unrelated systems.

Supported versions are the latest `main` branch and most recent tagged release.
Dependency updates and secret/vulnerability scans run in CI.

Production deployments must replace demo bearer tokens and database passwords
with a managed identity provider and secret manager; enable TLS; restrict network
paths; configure backups and retention; centralize immutable audit logs; and
complete a privacy, threat-model, and Snowflake-role review.

Logs, errors, traces, metrics, and Airflow XCom values must never contain names,
personal email, phone, date of birth, salary values, or raw rejected payloads.

