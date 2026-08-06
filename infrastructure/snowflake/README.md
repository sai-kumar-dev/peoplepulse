# Snowflake adapter

The local PostgreSQL path is authoritative for development and CI. Snowflake is
an optional warehouse adapter, isolated through dbt targets and environment
configuration.

1. Review `setup.sql` with a Snowflake security administrator.
2. Replace organizational parent-role grants and the example credit quota.
3. Run the account-level and security-level statements with the indicated roles.
4. Copy the Snowflake target from `dbt/profiles.yml.example` into your private
   `profiles.yml`, or supply its environment variables.
5. Run `dbt debug --target snowflake`, then `dbt build --target snowflake`.
6. Apply masking policies only after inspecting the columns emitted by dbt.

Clients should set a query tag containing service, environment, run ID, and model
name. `XSMALL` plus 60-second auto-suspend is the baseline, not a universal
recommendation. Resize from measured queue time and spill, then scale down again.

Operational guardrails:

- A monthly resource monitor warns at 75%, suspends at 90%, and hard-suspends at
  100%; tune quotas per account.
- Loading, transformation, and reporting use separate warehouses so noisy
  workloads cannot starve executive queries.
- Incremental models filter on effective/load timestamps to aid partition
  pruning; repeated full refreshes are discouraged.
- Use zero-copy clones for development and Time Travel for recovery, not as a
  substitute for backups or source replay.
- Secure views should expose aggregates only. Employee-level fields remain
  tagged and dynamically masked.

