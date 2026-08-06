"""Shared Airflow policies with PII-safe structured failure logs."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from airflow.models.taskinstance import TaskInstance

LOGGER = logging.getLogger("peoplepulse.airflow")

DEFAULT_ARGS: dict[str, Any] = {
    "owner": "people-analytics-engineering",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(minutes=20),
}


def log_failure(context: dict[str, Any]) -> None:
    """Log stable identifiers and exception type, never task inputs or source rows."""
    task_instance = context.get("task_instance")
    exception = context.get("exception")
    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "level": "ERROR",
        "service": "airflow",
        "environment": "local",
        "dag_id": getattr(task_instance, "dag_id", None),
        "task_id": getattr(task_instance, "task_id", None),
        "run_id": context.get("run_id"),
        "status": "failed",
        "error_code": "PIPELINE_TASK_FAILED",
        "exception_type": type(exception).__name__ if exception else "Unknown",
    }
    LOGGER.error(json.dumps(event, separators=(",", ":")))


def safe_run_metadata(task_instance: TaskInstance) -> dict[str, str | None]:
    return {
        "dag_id": task_instance.dag_id,
        "task_id": task_instance.task_id,
        "run_id": task_instance.run_id,
    }
