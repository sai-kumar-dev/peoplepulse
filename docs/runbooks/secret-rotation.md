# Runbook: secret rotation

1. Identify consumers and owners without copying the secret value.
2. Create a new credential with equal or narrower privileges in the deployment
   secret manager.
3. Update one service at a time and verify readiness, authentication failures,
   and audit events.
4. Revoke the old credential after all consumers are healthy. If compromise is
   suspected, revoke first and accept controlled downtime.
5. Rotate dependent tokens/keys and review access logs for unusual use.
6. Confirm `.env`, logs, Airflow XCom, CI artifacts, and Git history contain no
   value. If a value entered Git history, treat it as permanently disclosed.

The checked-in local demo tokens are not production secrets and must never be
reused outside an isolated development machine.

