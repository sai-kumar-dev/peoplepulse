# Runbook: failed ingestion

1. Find the failed run and task without printing XCom row payloads:

   ```bash
   docker compose exec airflow-scheduler airflow dags list-runs -d people_data_ingestion
   docker compose exec airflow-scheduler airflow tasks states-for-dag-run people_data_ingestion <run-id>
   ```

2. Inspect the task log in the Airflow UI or:

   ```bash
   docker compose exec airflow-scheduler airflow tasks logs people_data_ingestion <task-id> <run-id>
   ```

3. Classify the stable error code. Restore source availability for
   `SOURCE_UNAVAILABLE`; compare headers for `SCHEMA_DRIFT_DETECTED`; inspect
   database health for `LOAD_FAILED`.
4. Query `audit.pipeline_batch` and aggregate dead-letter counts. Do not export
   raw rejected payloads into tickets or chat.
5. Correct the source/configuration, then clear only the first safe failed task:

   ```bash
   docker compose exec airflow-scheduler airflow tasks clear people_data_ingestion --start-date YYYY-MM-DD --end-date YYYY-MM-DD --task-regex '<task-id>' --yes
   ```

6. Confirm source count = loaded + rejected + duplicates and that the checkpoint
   advanced once. Repeated loads must not increase business-key counts.

