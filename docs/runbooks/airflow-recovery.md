# Runbook: Airflow recovery

1. Check service health:

   ```bash
   docker compose ps
   docker compose exec airflow-scheduler airflow jobs check --job-type SchedulerJob
   ```

2. Restart an unhealthy stateless component without deleting metadata:

   ```bash
   docker compose restart airflow-scheduler
   ```

3. List runs and task states before clearing anything. Clear only failed/upstream
   failed tasks for the affected logical date; idempotency makes the replay safe.
4. Manual trigger:

   ```bash
   docker compose exec airflow-scheduler airflow dags trigger people_data_end_to_end --logical-date 2026-07-29T00:00:00+00:00
   ```

5. Backfill a bounded range:

   ```bash
   docker compose exec airflow-scheduler airflow dags backfill people_data_ingestion -s 2026-07-01 -e 2026-07-07
   ```

6. Single-task test:

   ```bash
   docker compose exec airflow-scheduler airflow tasks test people_data_ingestion validate_source_availability 2026-07-29
   ```

Do not delete Airflow metadata or generated raw batches as a recovery shortcut.

