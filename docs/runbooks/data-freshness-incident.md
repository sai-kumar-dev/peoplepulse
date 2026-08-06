# Runbook: data freshness incident

1. Confirm whether the source updated, ingestion completed, dbt published, and
   the API/dashboard cache expired. Freshness timestamps are technical UTC
   timestamps, not business-effective dates.
2. Find the last successful batch and its committed checkpoint.
3. If the source is late, notify consumers with the affected metrics and expected
   next check. Do not create fabricated replacement rows.
4. If the pipeline is late, follow the ingestion/dbt recovery runbook and replay
   from the checkpoint.
5. Verify source-to-target counts, quality status, mart maximum date, API
   `latest_refresh_time`, and dashboard value.
6. Record detection time, stale duration, cause, and prevention action.

