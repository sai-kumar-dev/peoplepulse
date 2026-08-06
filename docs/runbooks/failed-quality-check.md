# Runbook: failed quality check

1. Read `artifacts/data_quality/latest.json` or
   `audit.data_quality_result`. It contains safe counts, not failing rows.
2. Determine whether the check is critical or warning. Critical failures stop
   publication; warnings remain visible but do not block it.
3. Reproduce:

   ```bash
   docker compose run --rm api python -m peoplepulse.quality.cli
   docker compose run --rm dbt test --select <model-or-test>
   ```

4. Trace the affected entity to its batch ID. Inspect sensitive rows only in an
   approved restricted session, and record counts/IDs—not PII—in the incident.
5. Correct data through dead-letter reprocessing or correct transformation code.
   Do not weaken a threshold simply to make the pipeline green.
6. Rerun quality, transformation if needed, and publication. Attach before/after
   aggregate results to the incident.

