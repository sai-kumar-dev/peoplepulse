from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID

from data_generator import GenerationConfig, generate_dataset
from data_generator.generate import write_dataset
from data_generator.schemas import EMPLOYEE_SCHEMA
from ingestion.checkpoints import FileCheckpointStore, SQLiteCheckpointStore
from ingestion.cli import build_parser, load_directory
from ingestion.connectors import (
    CSVConnector,
    JSONConnector,
    PostgreSQLConnector,
    RESTConnector,
)
from ingestion.loaders import SQLiteRawLoader
from ingestion.pipeline import IngestionPipeline
from ingestion.reconciliation import reconcile_counts
from ingestion.validation import (
    RecordValidator,
    SchemaDriftDetector,
    infer_schema,
)
from peoplepulse.common.models import (
    Checkpoint,
    ExtractionContext,
    LoadContext,
)


def _contexts(batch_id: str) -> tuple[ExtractionContext, LoadContext]:
    return (
        ExtractionContext(
            batch_id=batch_id,
            source_name="hris_csv",
            entity_name="employees",
        ),
        LoadContext(
            batch_id=batch_id,
            pipeline_name="test_ingestion",
            source_name="hris_csv",
            entity_name="employees",
        ),
    )


def test_csv_pipeline_checkpoints_and_idempotently_deduplicates(
    tmp_path: Path,
) -> None:
    config = GenerationConfig(employees=20, months=12, seed=42)
    dataset = generate_dataset(config)
    write_dataset(tmp_path, config=config, formats=("csv",))
    checkpoint_store = FileCheckpointStore(tmp_path / "checkpoints.json")
    connector = CSVConnector(
        tmp_path / "employees.csv",
        entity_name="employees",
        source_name="hris_csv",
        schema=EMPLOYEE_SCHEMA,
        checkpoint_store=checkpoint_store,
    )
    loader = SQLiteRawLoader(tmp_path / "raw.db")
    validator = RecordValidator(
        EMPLOYEE_SCHEMA,
        known_departments={str(item["department_id"]) for item in dataset.departments},
        as_of_date=date(2025, 1, 31),
    )
    extraction, load = _contexts("batch-1")

    first = IngestionPipeline(loader).run(
        connector,
        extraction_context=extraction,
        load_context=load,
        validator=validator,
    )

    assert first.checkpoint_committed
    assert first.load_result.metadata.loaded_count == 20
    assert first.load_result.reconciliation
    assert first.load_result.reconciliation.matched
    checkpoint = connector.get_checkpoint()
    assert checkpoint
    assert checkpoint.value == 20
    assert len(loader.fetch_records("employees")) == 20

    extraction_2, load_2 = _contexts("batch-2")
    incremental = IngestionPipeline(loader).run(
        connector,
        extraction_context=extraction_2,
        load_context=load_2,
        validator=validator,
    )
    assert incremental.load_result.metadata.extracted_count == 0

    full_extraction = ExtractionContext(
        batch_id="batch-3",
        source_name="hris_csv",
        entity_name="employees",
        since=0,
    )
    full_load = LoadContext(
        batch_id="batch-3",
        pipeline_name="test_ingestion",
        source_name="hris_csv",
        entity_name="employees",
    )
    repeated = IngestionPipeline(loader).run(
        connector,
        extraction_context=full_extraction,
        load_context=full_load,
        validator=validator,
    )
    assert repeated.load_result.metadata.loaded_count == 0
    assert repeated.load_result.metadata.duplicate_count == 20
    assert len(loader.fetch_records("employees")) == 20
    loader.close()


def test_bad_record_goes_to_dead_letter_and_can_be_reprocessed(
    tmp_path: Path,
) -> None:
    dataset = generate_dataset(
        employees=12,
        months=12,
        scenario="deliberate_bad_record",
        seed=4,
    )
    loader = SQLiteRawLoader(tmp_path / "dead-letter.db")
    context = LoadContext(
        batch_id="bad-batch",
        pipeline_name="test_ingestion",
        source_name="hris",
        entity_name="employees",
    )

    result = loader.load(
        dataset.employees,
        context=context,
        schema=EMPLOYEE_SCHEMA,
    )

    assert result.metadata.loaded_count == 11
    assert result.metadata.rejected_count == 1
    assert result.reconciliation and result.reconciliation.matched
    pending = loader.get_dead_letters(status="pending")
    assert len(pending) == 1
    assert "employee_id:REQUIRED" in pending[0].validation_error

    corrected = dict(pending[0].payload)
    corrected.update(
        {
            "employee_id": "EMP-CORRECTED",
            "department_id": "DEP001",
            "hire_date": "2024-01-15",
        }
    )
    reprocessed = loader.reprocess_dead_letter(
        pending[0].dead_letter_id,
        corrected,
        context=LoadContext(
            batch_id="reprocess-batch",
            pipeline_name="test_ingestion",
            source_name="hris",
            entity_name="employees",
        ),
        schema=EMPLOYEE_SCHEMA,
    )
    assert reprocessed.metadata.loaded_count == 1
    assert not loader.get_dead_letters(status="pending")
    assert len(loader.get_dead_letters(status="resolved")) == 1
    loader.close()


def test_json_and_rest_connectors_support_typed_records_and_pagination(
    tmp_path: Path,
) -> None:
    path = tmp_path / "employees.json"
    records = [
        {"employee_id": "EMP1", "sequence": 1},
        {"employee_id": "EMP2", "sequence": 2},
    ]
    path.write_text(json.dumps({"records": records}), encoding="utf-8")
    json_connector = JSONConnector(path, entity_name="employees")
    context = ExtractionContext(
        batch_id="json-batch",
        source_name="json",
        entity_name="employees",
    )
    assert list(json_connector.extract(context)) == records
    assert json_connector.proposed_checkpoint
    assert json_connector.proposed_checkpoint.value == 2

    responses = {
        "page=2": {
            "records": [{"employee_id": "EMP2", "updated_at": "2025-01-02"}],
            "next": None,
        },
        "first": {
            "records": [{"employee_id": "EMP1", "updated_at": "2025-01-01"}],
            "next": "?page=2",
        },
    }

    def request(url: str, _headers: object, _timeout: float) -> object:
        return responses["page=2" if "page=2" in url else "first"]

    rest = RESTConnector(
        "https://synthetic.peoplepulse.example",
        "/employees",
        entity_name="employees",
        checkpoint_field="updated_at",
        requester=request,
        retries=0,
    )
    rest_context = ExtractionContext(
        batch_id="rest-batch",
        source_name="rest",
        entity_name="employees",
    )
    assert [item["employee_id"] for item in rest.extract(rest_context)] == [
        "EMP1",
        "EMP2",
    ]
    assert rest.proposed_checkpoint
    assert rest.proposed_checkpoint.value == "2025-01-02"


def test_schema_drift_reconciliation_and_sqlite_checkpoint(tmp_path: Path) -> None:
    observed = infer_schema(
        "employees",
        [
            {
                **{field.name: "value" for field in EMPLOYEE_SCHEMA.fields},
                "new_field": "new",
            }
        ],
    )
    drift = SchemaDriftDetector().detect(EMPLOYEE_SCHEMA, observed)
    assert drift.detected
    assert drift.added_fields == ("new_field",)

    reconciled = reconcile_counts(10, loaded_count=7, rejected_count=1, duplicate_count=2)
    assert reconciled.matched
    assert reconcile_counts(10, loaded_count=7).difference == 3

    store = SQLiteCheckpointStore(tmp_path / "checkpoints.db")
    checkpoint = Checkpoint("source", "employees", {"updated_at": "2025-01-01"})
    store.commit(checkpoint)
    restored = store.get("source", "employees")
    assert restored
    assert restored.value == checkpoint.value
    store.close()


def test_postgres_connector_uses_incremental_parameterized_query() -> None:
    executed: list[tuple[str, tuple[Any, ...]]] = []
    rows = [
        ("EMP1", "2025-01-01T00:00:00+00:00"),
        ("EMP2", "2025-01-02T00:00:00+00:00"),
    ]

    class FakeCursor:
        description = (("employee_id",), ("updated_at",))

        def execute(
            self,
            query: str,
            parameters: tuple[Any, ...] = (),
        ) -> None:
            executed.append((query, parameters))

        def fetchone(self) -> tuple[str, str]:
            return rows[0]

        def __iter__(self) -> Iterator[tuple[str, str]]:
            return iter(rows)

        def close(self) -> None:
            return None

    class FakeConnection:
        def cursor(self) -> FakeCursor:
            return FakeCursor()

        def close(self) -> None:
            return None

    connector = PostgreSQLConnector(
        "employees",
        schema_name="raw_hris",
        entity_name="employees",
        connection_factory=FakeConnection,
        checkpoint_column="updated_at",
        placeholder="?",
    )
    context = ExtractionContext(
        batch_id="pg-batch",
        source_name="postgresql",
        entity_name="employees",
        since="2024-12-31T00:00:00+00:00",
        limit=2,
    )

    extracted = list(connector.extract(context))

    assert [item["employee_id"] for item in extracted] == ["EMP1", "EMP2"]
    query, parameters = executed[-1]
    assert '"updated_at" > ?' in query
    assert "ORDER BY" in query
    assert parameters == ("2024-12-31T00:00:00+00:00", 2)
    assert connector.proposed_checkpoint
    assert connector.proposed_checkpoint.value == "2025-01-02T00:00:00+00:00"


def test_cli_loads_all_entities_and_full_rerun_is_idempotent(tmp_path: Path) -> None:
    source_dir = tmp_path / "source"
    database_path = tmp_path / "warehouse.db"
    write_dataset(
        source_dir,
        config=GenerationConfig(employees=10, months=12, seed=8),
        formats=("csv",),
    )
    parser = build_parser()
    first_args = parser.parse_args(
        [
            "load",
            "--input-dir",
            str(source_dir),
            "--database-url",
            f"sqlite:///{database_path}",
            "--batch-id",
            "parent-batch-1",
            "--full-refresh",
        ]
    )
    first = load_directory(first_args)

    assert first["status"] == "completed"
    assert first["entities"]["employees"]["loaded_count"] == 10
    UUID(first["entities"]["employees"]["batch_id"])

    second_args = parser.parse_args(
        [
            "load",
            "--input-dir",
            str(source_dir),
            "--database-url",
            f"sqlite:///{database_path}",
            "--batch-id",
            "parent-batch-2",
            "--full-refresh",
        ]
    )
    second = load_directory(second_args)

    assert second["entities"]["departments"]["loaded_count"] == 0
    assert second["entities"]["departments"]["duplicate_count"] == 8
    assert second["entities"]["employees"]["loaded_count"] == 0
    assert second["entities"]["employees"]["duplicate_count"] == 10
