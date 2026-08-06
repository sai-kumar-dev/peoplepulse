# Runbook: schema drift

1. Stop checkpoint advancement for the entity; preserve the source extract.
2. Compare connector `SourceSchema` with observed headers/types and classify the
   change as additive, compatible, breaking, or suspicious.
3. For an additive nullable field, update the source contract, raw DDL, staging
   model, catalog, and tests in one reviewed change. Do not auto-expose it.
4. For removed, renamed, or type-changed fields, quarantine the batch and agree a
   versioned migration with the source owner.
5. Run generator/connector tests, `dbt parse`, `dbt build`, and an idempotent
   replay in a disposable database.
6. Deploy, reprocess the quarantined batch, reconcile counts, and document the
   contract version and downstream impact.

