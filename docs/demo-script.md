# Five-minute demo

The demo uses only synthetic records. First copy local configuration:

```bash
cp .env.example .env
make demo
```

On Windows without GNU Make, run the equivalent commands:

```powershell
Copy-Item .env.example .env
docker compose up -d source-db warehouse airflow-db
docker compose run --rm api python -m data_generator.generate --employees 1000 --months 24 --seed 42 --scenario normal --output-dir /opt/peoplepulse/data/generated
docker compose run --rm api python -m ingestion.cli load --input-dir /opt/peoplepulse/data/generated
docker compose run --rm api python -m data_generator.generate --employees 1 --months 12 --seed 1337 --scenario deliberate_bad_record --output-dir /opt/peoplepulse/data/generated/deliberate_bad
docker compose run --rm api python -m ingestion.cli load --input-dir /opt/peoplepulse/data/generated/deliberate_bad
docker compose run --rm dbt deps
docker compose run --rm dbt build --target local
docker compose run --rm api python -m peoplepulse.quality.cli
docker compose up -d airflow-init airflow-webserver airflow-scheduler airflow-triggerer api dashboard
python scripts/demo_urls.py
```

## Narration and checks

1. **Synthetic sources (30 seconds).** Explain the seed and scenario flags. Show
   headers and counts, not names/contact values:

   ```bash
   docker compose run --rm api python -m data_generator.generate --employees 20 --months 12 --seed 42 --output-dir /tmp/repeat-a
   docker compose run --rm api python -m data_generator.generate --employees 20 --months 12 --seed 42 --output-dir /tmp/repeat-b
   ```

2. **Airflow flow (30 seconds).** Open <http://localhost:8080>, show the four
   DAGs, and trigger `people_data_end_to_end`.

3. **Raw batch and idempotency (35 seconds).** Run ingestion a second time and
   show that duplicates are accounted for instead of creating new business
   events. Query only metadata:

   ```bash
   docker compose exec warehouse psql -U peoplepulse -d people_warehouse -c "select batch_id,status,extracted_count,loaded_count,rejected_count,duplicate_count from audit.pipeline_batch order by started_at desc limit 8;"
   ```

4. **Rejected record (25 seconds).** The optional deliberate bad record has an
   invalid employment date. Show the rejection reason/count, never its payload:

   ```bash
   docker compose exec warehouse psql -U peoplepulse -d people_warehouse -c "select entity_name,validation_error,count(*) from audit.dead_letter_record group by 1,2;"
   ```

5. **dbt lineage and quality (35 seconds).** Explain raw → staging →
   intermediate → core → marts. Open generated dbt docs or show:

   ```bash
   docker compose run --rm dbt ls --resource-type model
   docker compose run --rm dbt test --target local
   ```

6. **SCD2 history (35 seconds).** Point out half-open effective ranges:

   ```bash
   docker compose exec warehouse psql -U peoplepulse -d people_warehouse -c "select employee_id,department_id,job_level,valid_from,valid_to,is_current from core.dim_employee where employee_id in (select employee_id from core.dim_employee group by 1 having count(*) > 1 limit 1) order by valid_from;"
   ```

7. **Governed API (30 seconds).**

   ```bash
   curl http://localhost:8000/health/dependencies
   curl http://localhost:8000/api/v1/workforce/summary
   curl http://localhost:8000/api/v1/data-quality
   ```

   Open <http://localhost:8000/docs> and note aggregate response models, bound
   filters, request IDs, and RFC 7807 errors.

8. **Executive dashboard (30 seconds).** Open <http://localhost:8501>. Show
   summary KPIs, headcount/attrition trends, quality, and pipeline health.

9. **PII boundary (20 seconds).** Call the catalog/classification endpoint and
   explain that workforce endpoints expose no names, email, phone, birth date, or
   raw salary. Demonstrate the admin route rejects a missing token:

   ```bash
   curl -i -X POST http://localhost:8000/api/v1/admin/trigger-ingestion
   ```

10. **Operational close (10 seconds).** Show JSON logs and the failed-ingestion
    runbook. Emphasize replay from committed checkpoints and measured Snowflake
    cost controls.
