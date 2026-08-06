"""Execute and publish critical and warning-level data-quality checks."""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta

from _common import DEFAULT_ARGS, log_failure
from airflow.decorators import dag, task


@dag(
    dag_id="people_data_quality",
    description="Freshness, volume, duplicate, referential, and business-rule gates.",
    schedule=None,
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    dagrun_timeout=timedelta(hours=1),
    tags=["peoplepulse", "quality"],
    on_failure_callback=log_failure,
)
def build_quality_dag() -> None:
    @task
    def evaluate_category(category: str) -> dict[str, str]:
        # Category-specific dbt selectors can be expanded without changing the
        # DAG contract. Aggregate checks run after all categories are declared.
        return {"category": category, "status": "scheduled"}

    @task(pool="warehouse_heavy")
    def publish_quality_summary(categories: list[dict[str, str]]) -> dict[str, object]:
        command = [
            "python",
            "-m",
            "peoplepulse.quality.cli",
            "--output",
            "/opt/peoplepulse/artifacts/data_quality/latest.json",
        ]
        completed = subprocess.run(command, check=True, capture_output=True, text=True)  # noqa: S603
        return {
            "categories": [item["category"] for item in categories],
            "status": "passed",
            "output_tail": completed.stdout[-1000:],
        }

    @task
    def alert_on_critical_failures(summary: dict[str, object]) -> None:
        # A non-zero quality CLI exit fails the upstream task. This task is the
        # extension point for Slack/email/PagerDuty and emits only safe metadata.
        print(json.dumps({"alert": "none", **summary}, separators=(",", ":")))

    categories = [
        evaluate_category.override(task_id=f"{name}_checks")(name)
        for name in ("freshness", "volume", "duplicate", "referential_integrity", "business_rule")
    ]
    summary = publish_quality_summary(categories)
    alert_on_critical_failures(summary)


people_data_quality = build_quality_dag()
