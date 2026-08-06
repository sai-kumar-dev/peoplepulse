# Runbook: database restore

1. Declare whether the source simulator, warehouse, or Airflow metadata database
   is affected. Stop writers to that database.
2. Snapshot/backup the damaged state for investigation.
3. Restore the most recent tested PostgreSQL backup into a new named database or
   volume; never overwrite the only copy before verification.
4. Run schema version checks, aggregate row-count checks, and latest-batch
   reconciliation. Validate a point-in-time SCD query and workforce summary.
5. Redirect one non-production client, run the end-to-end smoke test, then cut
   over all services.
6. Replay raw batches newer than the restore point from committed checkpoints.
   Confirm no duplicate business events and record recovery point/time.

Local demo volumes are disposable and contain only generated data. They may be
recreated with `docker compose down -v` only when the operator explicitly
accepts losing local state.

