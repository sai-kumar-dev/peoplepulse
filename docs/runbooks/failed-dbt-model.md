# Runbook: failed dbt model

1. Open `dbt/target/run_results.json` or the Airflow transformation task log.
2. Reproduce only the failed model:

   ```bash
   docker compose run --rm dbt run --select <model>+ --target local
   docker compose run --rm dbt test --select <model>+ --target local
   ```

3. If compilation failed, run `dbt compile --select <model>`. If execution
   failed, inspect warehouse locks, storage, and the generated SQL under
   `dbt/target/run`.
4. Never bypass a failing model with a manual mart edit. Fix SQL or source data,
   review upstream reconciliation, and rerun the selector.
5. Resume the Airflow DAG only after dbt tests pass and compare affected mart
   totals to the preceding successful run.

