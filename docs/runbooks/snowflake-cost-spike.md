# Runbook: Snowflake cost spike

1. Check the resource-monitor notification, warehouse credit history, query
   history, and query tags. Attribute spend to service/run/model.
2. Suspend the offending warehouse if the increase is uncontrolled:

   ```sql
   ALTER WAREHOUSE PEOPLEPULSE_TRANSFORMING SUSPEND;
   ```

3. Look for accidental full refreshes, unbounded date predicates, Cartesian
   joins, queue-driven over-scaling, or dashboards bypassing marts.
4. Cancel only identified runaway queries. Preserve query IDs and profiles.
5. Fix and test using a zero-copy development clone and an `XSMALL` warehouse.
6. Resume with conservative sizing, verify auto-suspend/resource-monitor
   assignment, and compare credits per processed row to baseline.

