"""CLI for loading generated source files into the raw warehouse."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from data_generator.schemas import SCHEMAS
from ingestion.checkpoints import FileCheckpointStore
from ingestion.connectors import CSVConnector, JSONConnector
from ingestion.loaders import PostgreSQLRawLoader, SQLiteRawLoader
from ingestion.pipeline import IngestionPipeline
from ingestion.validation import RecordValidator
from peoplepulse.common.models import ExtractionContext, LoadContext


def _sqlite_path(database_url: str) -> str:
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError("unsupported SQLite database URL")
    value = database_url[len(prefix) :]
    return ":memory:" if value == ":memory:" else value


def _postgres_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _make_loader(
    database_url: str,
    *,
    fail_on_schema_drift: bool,
) -> SQLiteRawLoader | PostgreSQLRawLoader:
    if database_url.startswith("sqlite:///"):
        return SQLiteRawLoader(
            _sqlite_path(database_url),
            fail_on_schema_drift=fail_on_schema_drift,
        )
    if database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        return PostgreSQLRawLoader(
            _postgres_dsn(database_url),
            fail_on_schema_drift=fail_on_schema_drift,
        )
    raise ValueError("database URL must use sqlite:/// or postgresql://")


def _department_ids(path: Path, file_format: str) -> set[str]:
    schema = SCHEMAS["departments"]
    connector = (
        CSVConnector(path, entity_name="departments", schema=schema)
        if file_format == "csv"
        else JSONConnector(path, entity_name="departments", schema=schema)
    )
    context = ExtractionContext(
        batch_id="reference-read",
        source_name=connector.source_name,
        entity_name="departments",
        since=0,
    )
    return {
        str(record["department_id"])
        for record in connector.extract(context)
        if record.get("department_id")
    }


def _validation_as_of_date(
    input_dir: Path,
    explicit_value: date | None,
) -> date | None:
    if explicit_value is not None:
        return explicit_value
    manifest_path = input_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    value = manifest.get("config", {}).get("as_of_date")
    return date.fromisoformat(str(value)) if value else None


def load_directory(args: argparse.Namespace) -> dict[str, Any]:
    input_dir = Path(args.input_dir)
    if not input_dir.is_dir():
        raise FileNotFoundError(f"input directory not found: {input_dir}")
    database_url = args.database_url or os.getenv(
        "PEOPLEPULSE_WAREHOUSE_DATABASE_URL",
        "sqlite:///peoplepulse_raw.db",
    )
    loader = _make_loader(
        database_url,
        fail_on_schema_drift=args.fail_on_schema_drift,
    )
    batch_id = args.batch_id or str(uuid4())
    checkpoint_path = args.checkpoint_file or input_dir / ".ingestion_checkpoints.json"
    checkpoint_store = FileCheckpointStore(checkpoint_path)
    departments_path = input_dir / f"departments.{args.file_format}"
    known_departments = _department_ids(departments_path, args.file_format)
    validation_as_of_date = _validation_as_of_date(input_dir, args.as_of_date)
    entities: dict[str, dict[str, Any]] = {}
    try:
        for entity_name, schema in SCHEMAS.items():
            path = input_dir / f"{entity_name}.{args.file_format}"
            if not path.is_file():
                raise FileNotFoundError(f"required source file not found: {path}")
            connector = (
                CSVConnector(
                    path,
                    entity_name=entity_name,
                    source_name=f"hris_{args.file_format}",
                    schema=schema,
                    checkpoint_store=checkpoint_store,
                )
                if args.file_format == "csv"
                else JSONConnector(
                    path,
                    entity_name=entity_name,
                    source_name=f"hris_{args.file_format}",
                    schema=schema,
                    checkpoint_store=checkpoint_store,
                )
            )
            # Raw warehouse metadata uses UUID keys. Deriving an entity load UUID
            # preserves the caller's parent batch identity without key collisions.
            entity_batch_id = str(uuid5(NAMESPACE_URL, f"peoplepulse:{batch_id}:{entity_name}"))
            extraction_context = ExtractionContext(
                batch_id=entity_batch_id,
                source_name=connector.source_name,
                entity_name=entity_name,
                since=0 if args.full_refresh else None,
            )
            load_context = LoadContext(
                batch_id=entity_batch_id,
                pipeline_name="people_data_ingestion",
                source_name=connector.source_name,
                entity_name=entity_name,
            )
            validator = RecordValidator(
                schema,
                known_departments=(
                    known_departments if "department_id" in schema.field_names else None
                ),
                as_of_date=validation_as_of_date,
                reject_unknown_fields=args.fail_on_schema_drift,
            )
            result = IngestionPipeline(loader).run(
                connector,
                extraction_context=extraction_context,
                load_context=load_context,
                validator=validator,
            )
            metadata = result.load_result.metadata
            entities[entity_name] = {
                "batch_id": metadata.batch_id,
                "status": metadata.status.value,
                "extracted_count": metadata.extracted_count,
                "loaded_count": metadata.loaded_count,
                "rejected_count": metadata.rejected_count,
                "duplicate_count": metadata.duplicate_count,
                "checkpoint_committed": result.checkpoint_committed,
            }
    finally:
        close = getattr(loader, "close", None)
        if callable(close):
            close()
    return {
        "batch_id": batch_id,
        "database_backend": database_url.split(":", 1)[0],
        "entities": entities,
        "status": "completed",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PeoplePulse source ingestion")
    subparsers = parser.add_subparsers(dest="command", required=True)
    load = subparsers.add_parser("load", help="load generated HRIS source files")
    load.add_argument("--input-dir", type=Path, required=True)
    load.add_argument("--batch-id")
    load.add_argument("--database-url")
    load.add_argument("--file-format", choices=("csv", "json"), default="csv")
    load.add_argument("--checkpoint-file", type=Path)
    load.add_argument("--full-refresh", action="store_true")
    load.add_argument("--fail-on-schema-drift", action="store_true")
    load.add_argument("--as-of-date", type=date.fromisoformat)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "load":
        summary = load_directory(args)
        print(json.dumps(summary, sort_keys=True))
        return 0
    raise AssertionError(f"unsupported command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
