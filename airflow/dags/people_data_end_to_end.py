"""Sequentially trigger ingestion, transformation, and quality pipelines."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from _common import DEFAULT_ARGS, log_failure
from airflow.operators.empty import EmptyOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator

from airflow import DAG

with DAG(
    dag_id="people_data_end_to_end",
    description="End-to-end publication pipeline for trusted workforce metrics.",
    schedule="0 1 * * *",
    start_date=datetime(2025, 1, 1, tzinfo=UTC),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    dagrun_timeout=timedelta(hours=4),
    tags=["peoplepulse", "end-to-end"],
    on_failure_callback=log_failure,
) as people_data_end_to_end:
    start = EmptyOperator(task_id="start")
    ingestion = TriggerDagRunOperator(
        task_id="run_ingestion",
        trigger_dag_id="people_data_ingestion",
        wait_for_completion=True,
        poke_interval=30,
        reset_dag_run=True,
        allowed_states=["success"],
        failed_states=["failed"],
        conf={"logical_date": "{{ ds }}"},
    )
    transformation = TriggerDagRunOperator(
        task_id="run_transformation",
        trigger_dag_id="people_data_transformation",
        wait_for_completion=True,
        poke_interval=30,
        reset_dag_run=True,
        allowed_states=["success"],
        failed_states=["failed"],
        conf={"logical_date": "{{ ds }}"},
    )
    quality = TriggerDagRunOperator(
        task_id="run_data_quality",
        trigger_dag_id="people_data_quality",
        wait_for_completion=True,
        poke_interval=30,
        reset_dag_run=True,
        allowed_states=["success"],
        failed_states=["failed"],
        conf={"logical_date": "{{ ds }}"},
    )
    published = EmptyOperator(task_id="metrics_published")

    start >> ingestion >> transformation >> quality >> published
