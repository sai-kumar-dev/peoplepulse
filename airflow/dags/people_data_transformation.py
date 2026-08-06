"""Build tested dimensional models and analytics marts with dbt."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import UTC, datetime, timedelta

from _common import DEFAULT_ARGS, log_failure
from airflow.decorators import dag, task

DBT_PROJECT_DIR = "/opt/peoplepulse/dbt"


def _dbt(*arguments: str) -> dict[str, object]:
    started = time.monotonic()
    command = [
        "dbt",
        *arguments,
        "--project-dir",
        DBT_PROJECT_DIR,
        "--profiles-dir",
        DBT_PROJECT_DIR,
    ]
    completed = subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603
    return {
        "command": " ".join(command[:2]),
        "duration_ms": round((time.monotonic() - started) * 1000),
        "status": "completed",
        "output_tail": completed.stdout[-1000:],
    }


@dag(
    dag_id="people_data_transformation",
    description="Layered dbt transformations from staging through governed marts.",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    dagrun_timeout=timedelta(hours=2),
    tags=["peoplepulse", "dbt"],
    on_failure_callback=log_failure,
)
def build_transformation_dag() -> None:
    @task
    def run_dbt_deps() -> dict[str, object]:
        return _dbt("deps")

    @task(pool="warehouse_heavy")
    def run_reference_seeds(_: dict[str, object]) -> dict[str, object]:
        return _dbt("seed")

    @task(pool="warehouse_heavy")
    def snapshot_mutable_sources(_: dict[str, object]) -> dict[str, object]:
        return _dbt("snapshot")

    @task(pool="warehouse_heavy")
    def run_staging_models(_: dict[str, object]) -> dict[str, object]:
        return _dbt("run", "--select", "path:models/staging")

    @task(pool="warehouse_heavy")
    def run_intermediate_models(_: dict[str, object]) -> dict[str, object]:
        return _dbt("run", "--select", "path:models/intermediate")

    @task(pool="warehouse_heavy")
    def run_core_dimensions(_: dict[str, object]) -> dict[str, object]:
        return _dbt("run", "--select", "path:models/core/dim*")

    @task(pool="warehouse_heavy")
    def run_facts(_: dict[str, object]) -> dict[str, object]:
        return _dbt("run", "--select", "path:models/core/fact*")

    @task(pool="warehouse_heavy")
    def run_marts(_: dict[str, object]) -> dict[str, object]:
        return _dbt("run", "--select", "path:models/marts")

    @task(pool="warehouse_heavy")
    def run_dbt_tests(_: dict[str, object]) -> dict[str, object]:
        return _dbt("test")

    @task
    def generate_dbt_docs(_: dict[str, object]) -> dict[str, object]:
        return _dbt("docs", "generate")

    @task
    def record_transformation_status(result: dict[str, object]) -> None:
        print(json.dumps({"pipeline": "transformation", **result}, separators=(",", ":")))

    deps = run_dbt_deps()
    seeds = run_reference_seeds(deps)
    snapshots = snapshot_mutable_sources(seeds)
    staging = run_staging_models(snapshots)
    intermediate = run_intermediate_models(staging)
    dimensions = run_core_dimensions(intermediate)
    facts = run_facts(dimensions)
    marts = run_marts(facts)
    tests = run_dbt_tests(marts)
    docs = generate_dbt_docs(tests)
    record_transformation_status(docs)


people_data_transformation = build_transformation_dag()
