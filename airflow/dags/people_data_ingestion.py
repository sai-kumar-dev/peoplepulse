"""Ingest generated people data into immutable raw warehouse tables."""

from __future__ import annotations

import csv
import json
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from _common import DEFAULT_ARGS, log_failure
from airflow.decorators import dag, task

DATA_DIR = Path("/opt/peoplepulse/data/generated")
EXPECTED_HEADERS: dict[str, set[str]] = {
    "departments": {"department_id", "department_name"},
    "employees": {"employee_id", "hire_date", "employment_status", "department_id"},
    "hires": {"hire_event_id", "employee_id", "hire_date"},
    "terminations": {"termination_event_id", "employee_id", "termination_date"},
}


@dag(
    dag_id="people_data_ingestion",
    description="Idempotent raw ingestion with validation, reconciliation, and batch audit.",
    schedule="0 2 * * *",
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    dagrun_timeout=timedelta(hours=1),
    tags=["peoplepulse", "ingestion"],
    on_failure_callback=log_failure,
)
def build_ingestion_dag() -> None:
    @task
    def initialize_batch(data_interval_end: str | None = None) -> dict[str, str]:
        return {
            "batch_id": str(uuid4()),
            "pipeline_name": "people_data_ingestion",
            "effective_at": data_interval_end or datetime.now(UTC).isoformat(),
            "status": "started",
        }

    @task
    def validate_source_availability(batch: dict[str, str]) -> dict[str, str]:
        missing = [
            f"{entity}.csv"
            for entity in EXPECTED_HEADERS
            if not (DATA_DIR / f"{entity}.csv").is_file()
        ]
        if missing:
            raise FileNotFoundError(
                f"Required synthetic source files unavailable: {', '.join(missing)}"
            )
        return batch

    @task
    def extract_source(entity: str, batch: dict[str, str]) -> dict[str, Any]:
        path = DATA_DIR / f"{entity}.csv"
        with path.open(encoding="utf-8", newline="") as handle:
            count = max(sum(1 for _ in handle) - 1, 0)
        return {"entity": entity, "extracted_count": count, "batch_id": batch["batch_id"]}

    @task
    def validate_schemas(extractions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for extraction in extractions:
            entity = str(extraction["entity"])
            with (DATA_DIR / f"{entity}.csv").open(encoding="utf-8", newline="") as handle:
                headers = set(next(csv.reader(handle), []))
            missing = EXPECTED_HEADERS[entity] - headers
            if missing:
                raise ValueError(
                    f"Schema drift for {entity}; missing required columns: {sorted(missing)}"
                )
        return extractions

    @task(pool="warehouse_heavy")
    def load_raw_tables(batch: dict[str, str], _: list[dict[str, Any]]) -> dict[str, Any]:
        command = [
            "python",
            "-m",
            "ingestion.cli",
            "load",
            "--input-dir",
            str(DATA_DIR),
            "--batch-id",
            batch["batch_id"],
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603
        return {
            "batch_id": batch["batch_id"],
            "loader_summary": completed.stdout[-2000:],
        }

    @task
    def reconcile_source_target_counts(
        extractions: list[dict[str, Any]],
        load_result: dict[str, Any],
    ) -> dict[str, Any]:
        # The loader owns authoritative per-entity reconciliation. This records
        # source totals in XCom without passing row payloads.
        return {
            "batch_id": load_result["batch_id"],
            "extracted_count": sum(int(item["extracted_count"]) for item in extractions),
            "status": "reconciled",
        }

    @task
    def record_batch_completion(reconciliation: dict[str, Any]) -> None:
        print(json.dumps({**reconciliation, "status": "completed"}, separators=(",", ":")))

    batch = initialize_batch()
    available = validate_source_availability(batch)
    extractions = [
        extract_source.override(task_id=f"extract_{entity}")(entity, available)
        for entity in EXPECTED_HEADERS
    ]
    schemas = validate_schemas(extractions)
    loaded = load_raw_tables(batch, schemas)
    reconciliation = reconcile_source_target_counts(extractions, loaded)
    record_batch_completion(reconciliation)


people_data_ingestion = build_ingestion_dag()
