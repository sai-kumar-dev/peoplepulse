"""Transactional SQLite raw loader used by local runs and unit tests."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from ingestion.reconciliation import reconcile_counts
from ingestion.validation import RecordValidator, SchemaDriftDetector, infer_schema
from peoplepulse.common.errors import ErrorCode, PeoplePulseError
from peoplepulse.common.hashing import canonical_json, checksum_records, record_hash
from peoplepulse.common.models import (
    BatchMetadata,
    BatchStatus,
    DeadLetterRecord,
    LoadContext,
    LoadResult,
    Record,
    SchemaDrift,
    SourceSchema,
    utc_now,
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return f'"{value}"'


def _sqlite_type(data_type: str) -> str:
    return {
        "boolean": "INTEGER",
        "integer": "INTEGER",
        "number": "REAL",
    }.get(data_type, "TEXT")


def _db_value(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class SQLiteRawLoader:
    """Idempotent raw loader with audit, drift, and dead-letter tables.

    SQLite has no schemas, so ``raw_hris.employees`` is represented physically as
    ``raw_hris__employees``. A compatibility view named ``raw_employees`` is also
    created for ad-hoc local queries.
    """

    def __init__(
        self,
        database: str | Path = ":memory:",
        *,
        connection: sqlite3.Connection | None = None,
        raw_schema: str = "raw_hris",
        allow_schema_evolution: bool = True,
        fail_on_schema_drift: bool = False,
    ) -> None:
        _quote(raw_schema)
        self.raw_schema = raw_schema
        self.allow_schema_evolution = allow_schema_evolution
        self.fail_on_schema_drift = fail_on_schema_drift
        self._owns_connection = connection is None
        self.connection = connection or sqlite3.connect(str(database))
        self.connection.row_factory = sqlite3.Row
        self._initialize_audit_tables()

    def _initialize_audit_tables(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS ingestion_batches (
                batch_id TEXT PRIMARY KEY,
                pipeline_name TEXT NOT NULL,
                source_name TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                status TEXT NOT NULL,
                extracted_count INTEGER NOT NULL DEFAULT 0,
                loaded_count INTEGER NOT NULL DEFAULT 0,
                rejected_count INTEGER NOT NULL DEFAULT 0,
                duplicate_count INTEGER NOT NULL DEFAULT 0,
                checksum TEXT NOT NULL DEFAULT '',
                checkpoint_value TEXT,
                error_code TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS ingestion_record_keys (
                source_name TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                first_batch_id TEXT NOT NULL,
                first_loaded_at TEXT NOT NULL,
                PRIMARY KEY (source_name, entity_name, record_hash)
            );

            CREATE TABLE IF NOT EXISTS dead_letter_records (
                dead_letter_id TEXT PRIMARY KEY,
                payload_json TEXT NOT NULL,
                source_identifier TEXT NOT NULL,
                validation_error TEXT NOT NULL,
                batch_id TEXT NOT NULL,
                rejected_at TEXT NOT NULL,
                reprocessing_status TEXT NOT NULL DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS schema_drift_events (
                drift_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                added_fields_json TEXT NOT NULL,
                missing_fields_json TEXT NOT NULL,
                type_changes_json TEXT NOT NULL,
                detected_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_dead_letter_batch
                ON dead_letter_records (batch_id, reprocessing_status);
            CREATE INDEX IF NOT EXISTS idx_batches_entity_started
                ON ingestion_batches (entity_name, started_at);
            """
        )
        self.connection.commit()

    def physical_table_name(self, entity_name: str) -> str:
        _quote(entity_name)
        return f"{self.raw_schema}__{entity_name}"

    def _existing_columns(self, table_name: str) -> set[str]:
        rows = self.connection.execute(f"PRAGMA table_info({_quote(table_name)})").fetchall()
        return {str(row["name"]) for row in rows}

    def _ensure_entity_table(
        self,
        schema: SourceSchema,
        extra_fields: Iterable[str] = (),
    ) -> None:
        table_name = self.physical_table_name(schema.entity_name)
        definitions = [
            f"{_quote(field.name)} {_sqlite_type(field.data_type)}" for field in schema.fields
        ]
        definitions.extend(
            (
                '"_ingested_at" TEXT NOT NULL',
                '"_batch_id" TEXT NOT NULL',
            )
        )
        self.connection.execute(
            f"CREATE TABLE IF NOT EXISTS {_quote(table_name)} ({', '.join(definitions)})"
        )
        existing = self._existing_columns(table_name)
        if self.allow_schema_evolution:
            for field_name in sorted(set(extra_fields) - existing):
                _quote(field_name)
                self.connection.execute(
                    f"ALTER TABLE {_quote(table_name)} ADD COLUMN {_quote(field_name)} TEXT"
                )
        alias = f"raw_{schema.entity_name}"
        _quote(alias)
        self.connection.execute(
            f"CREATE VIEW IF NOT EXISTS {_quote(alias)} AS SELECT * FROM {_quote(table_name)}"
        )

    def _upsert_metadata(self, metadata: BatchMetadata) -> None:
        self.connection.execute(
            """
            INSERT INTO ingestion_batches (
                batch_id, pipeline_name, source_name, entity_name,
                started_at, completed_at, status, extracted_count,
                loaded_count, rejected_count, duplicate_count, checksum,
                checkpoint_value, error_code, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (batch_id) DO UPDATE SET
                pipeline_name = excluded.pipeline_name,
                source_name = excluded.source_name,
                entity_name = excluded.entity_name,
                started_at = excluded.started_at,
                completed_at = excluded.completed_at,
                status = excluded.status,
                extracted_count = excluded.extracted_count,
                loaded_count = excluded.loaded_count,
                rejected_count = excluded.rejected_count,
                duplicate_count = excluded.duplicate_count,
                checksum = excluded.checksum,
                checkpoint_value = excluded.checkpoint_value,
                error_code = excluded.error_code,
                error_message = excluded.error_message
            """,
            (
                metadata.batch_id,
                metadata.pipeline_name,
                metadata.source_name,
                metadata.entity_name,
                metadata.started_at.isoformat(),
                metadata.completed_at.isoformat() if metadata.completed_at else None,
                metadata.status.value,
                metadata.extracted_count,
                metadata.loaded_count,
                metadata.rejected_count,
                metadata.duplicate_count,
                metadata.checksum,
                metadata.checkpoint_value,
                metadata.error_code,
                metadata.error_message,
            ),
        )

    def _record_drift(
        self,
        context: LoadContext,
        drift: SchemaDrift,
    ) -> None:
        if not drift.detected:
            return
        self.connection.execute(
            """
            INSERT INTO schema_drift_events (
                drift_id, batch_id, source_name, entity_name,
                added_fields_json, missing_fields_json, type_changes_json,
                detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                context.batch_id,
                context.source_name,
                context.entity_name,
                json.dumps(drift.added_fields),
                json.dumps(drift.missing_fields),
                json.dumps(dict(drift.type_changes), sort_keys=True),
                utc_now().isoformat(),
            ),
        )

    @staticmethod
    def _source_identifier(
        record: Mapping[str, Any],
        schema: SourceSchema,
    ) -> str:
        values = [str(record.get(key) or "") for key in schema.business_key]
        if values and all(values):
            return "|".join(values)
        return f"hash:{record_hash(record)[:16]}"

    def _store_dead_letter(
        self,
        record: Mapping[str, Any],
        schema: SourceSchema,
        context: LoadContext,
        errors: str,
    ) -> DeadLetterRecord:
        dead_letter = DeadLetterRecord(
            dead_letter_id=str(uuid4()),
            payload=dict(record),
            source_identifier=self._source_identifier(record, schema),
            validation_error=errors,
            batch_id=context.batch_id,
        )
        self.connection.execute(
            """
            INSERT INTO dead_letter_records (
                dead_letter_id, payload_json, source_identifier,
                validation_error, batch_id, rejected_at, reprocessing_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dead_letter.dead_letter_id,
                canonical_json(dead_letter.payload),
                dead_letter.source_identifier,
                dead_letter.validation_error,
                dead_letter.batch_id,
                dead_letter.rejected_at.isoformat(),
                dead_letter.reprocessing_status,
            ),
        )
        return dead_letter

    def _insert_record(
        self,
        record: Mapping[str, Any],
        schema: SourceSchema,
        context: LoadContext,
        extra_fields: set[str],
    ) -> bool:
        item_hash = record_hash(record)
        cursor = self.connection.execute(
            """
            INSERT OR IGNORE INTO ingestion_record_keys (
                source_name, entity_name, record_hash,
                first_batch_id, first_loaded_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                context.source_name,
                context.entity_name,
                item_hash,
                context.batch_id,
                utc_now().isoformat(),
            ),
        )
        if cursor.rowcount == 0:
            return False
        columns = list(schema.field_names)
        if self.allow_schema_evolution:
            columns.extend(sorted(extra_fields))
        columns.extend(("_ingested_at", "_batch_id"))
        values = [_db_value(record.get(name)) for name in columns[:-2]]
        values.extend((utc_now().isoformat(), context.batch_id))
        placeholders = ", ".join("?" for _ in columns)
        column_sql = ", ".join(_quote(name) for name in columns)
        self.connection.execute(
            f"INSERT INTO {_quote(self.physical_table_name(schema.entity_name))} "
            f"({column_sql}) VALUES ({placeholders})",
            values,
        )
        return True

    def load(
        self,
        records: Iterable[Record],
        *,
        context: LoadContext,
        schema: SourceSchema,
        validator: RecordValidator | None = None,
    ) -> LoadResult:
        if context.entity_name != schema.entity_name:
            raise ValueError("load context entity does not match source schema")
        materialized = [dict(record) for record in records]
        metadata = BatchMetadata(
            batch_id=context.batch_id,
            pipeline_name=context.pipeline_name,
            source_name=context.source_name,
            entity_name=context.entity_name,
            started_at=context.started_at,
            extracted_count=len(materialized),
            checksum=checksum_records(materialized),
            checkpoint_value=context.checkpoint_value,
        )
        dead_letters: list[DeadLetterRecord] = []
        observed = infer_schema(schema.entity_name, materialized)
        drift = SchemaDriftDetector().detect(schema, observed) if materialized else SchemaDrift()
        extra_fields = set(drift.added_fields)
        validator = validator or RecordValidator(
            schema,
            reject_unknown_fields=self.fail_on_schema_drift,
        )

        try:
            with self.connection:
                self._upsert_metadata(metadata)
                self._ensure_entity_table(schema, extra_fields)
                self._record_drift(context, drift)
                for record in materialized:
                    validation = validator.validate(record)
                    if not validation.valid:
                        safe_errors = "; ".join(
                            f"{issue.field}:{issue.code}" for issue in validation.issues
                        )
                        dead_letters.append(
                            self._store_dead_letter(
                                record,
                                schema,
                                context,
                                safe_errors,
                            )
                        )
                        metadata.rejected_count += 1
                        continue
                    if self._insert_record(
                        record,
                        schema,
                        context,
                        extra_fields & set(record),
                    ):
                        metadata.loaded_count += 1
                    else:
                        metadata.duplicate_count += 1
                metadata.completed_at = utc_now()
                metadata.status = (
                    BatchStatus.COMPLETED_WITH_REJECTIONS
                    if metadata.rejected_count
                    else BatchStatus.COMPLETED
                )
                reconciliation = reconcile_counts(
                    metadata.extracted_count,
                    metadata.loaded_count,
                    metadata.rejected_count,
                    metadata.duplicate_count,
                )
                self._upsert_metadata(metadata)
        except (sqlite3.Error, ValueError, TypeError) as exc:
            metadata.completed_at = utc_now()
            metadata.status = BatchStatus.FAILED
            metadata.error_code = ErrorCode.LOAD_FAILED.value
            metadata.error_message = "Raw batch transaction failed."
            try:
                with self.connection:
                    self._upsert_metadata(metadata)
            except sqlite3.Error:
                pass
            raise PeoplePulseError(
                ErrorCode.LOAD_FAILED,
                "Raw batch transaction failed.",
                retryable=True,
                context={
                    "batch_id": context.batch_id,
                    "source": context.source_name,
                    "entity": context.entity_name,
                },
                cause=exc,
            ) from exc

        return LoadResult(
            metadata=metadata,
            dead_letters=tuple(dead_letters),
            reconciliation=reconciliation,
        )

    def fetch_records(self, entity_name: str) -> list[dict[str, Any]]:
        table_name = self.physical_table_name(entity_name)
        rows = self.connection.execute(f"SELECT * FROM {_quote(table_name)}").fetchall()
        return [dict(row) for row in rows]

    def get_batch(self, batch_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM ingestion_batches WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
        return dict(row) if row else None

    def get_dead_letters(
        self,
        *,
        status: str | None = None,
    ) -> list[DeadLetterRecord]:
        query = "SELECT * FROM dead_letter_records"
        parameters: tuple[Any, ...] = ()
        if status is not None:
            query += " WHERE reprocessing_status = ?"
            parameters = (status,)
        query += " ORDER BY rejected_at, dead_letter_id"
        rows = self.connection.execute(query, parameters).fetchall()
        return [
            DeadLetterRecord(
                dead_letter_id=row["dead_letter_id"],
                payload=json.loads(row["payload_json"]),
                source_identifier=row["source_identifier"],
                validation_error=row["validation_error"],
                batch_id=row["batch_id"],
                rejected_at=datetime.fromisoformat(row["rejected_at"]),
                reprocessing_status=row["reprocessing_status"],
            )
            for row in rows
        ]

    def reprocess_dead_letter(
        self,
        dead_letter_id: str,
        corrected_record: Record,
        *,
        context: LoadContext,
        schema: SourceSchema,
        validator: RecordValidator | None = None,
    ) -> LoadResult:
        existing = self.connection.execute(
            """
            SELECT dead_letter_id FROM dead_letter_records
            WHERE dead_letter_id = ? AND reprocessing_status = 'pending'
            """,
            (dead_letter_id,),
        ).fetchone()
        if existing is None:
            raise KeyError(f"pending dead letter not found: {dead_letter_id}")
        result = self.load(
            (corrected_record,),
            context=context,
            schema=schema,
            validator=validator,
        )
        if result.metadata.rejected_count == 0:
            with self.connection:
                self.connection.execute(
                    """
                    UPDATE dead_letter_records
                    SET reprocessing_status = 'resolved'
                    WHERE dead_letter_id = ?
                    """,
                    (dead_letter_id,),
                )
        return result

    def close(self) -> None:
        if self._owns_connection:
            self.connection.close()

    def __enter__(self) -> SQLiteRawLoader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
