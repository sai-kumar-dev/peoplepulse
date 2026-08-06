# Runbook: reprocess rejected records

1. Select pending rejects by batch, entity, and validation error. Never download
   unrestricted payloads to a workstation.
2. Correct the upstream synthetic source or create an approved corrected record.
   Keep the original rejection immutable.
3. Dry-run validation using the same schema and business-rule version as normal
   ingestion.
4. Reprocess through the admin API:

   ```bash
   curl -X POST http://localhost:8000/api/v1/admin/reprocess-rejected \
     -H "Authorization: Bearer local-admin-change-me" \
     -H "Content-Type: application/json" \
     -d '{"batch_id":"<batch-id>","dry_run":false}'
   ```

5. Confirm the raw row is present once, the dead-letter status is `reprocessed`,
   reconciliation balances, and downstream dbt/quality runs pass.

