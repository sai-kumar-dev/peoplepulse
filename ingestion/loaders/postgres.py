"""PostgreSQL raw-zone loader matching the ``raw_hris`` warehouse contract."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping
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


def _postgres_type(data_type: str) -> str:
    return {
        "boolean": "BOOLEAN",
        "integer": "BIGINT",
        "number": "NUMERIC",
        "date": "DATE",
        "datetime": "TIMESTAMPTZ",
        "object": "JSONB",
        "array": "JSONB",
    }.get(data_type, "TEXT")


class PostgreSQLRawLoader:
    """Transactional DB-API loader; imports psycopg only when a DSN is used."""

    def __init__(
        self,
        dsn: str | None = None,
        *,
        connection_factory: Callable[[], Any] | None = None,
        raw_schema: str = "raw_hris",
        audit_schema: str = "audit",
        allow_schema_evolution: bool = False,
        fail_on_schema_drift: bool = False,
    ) -> None:
        if dsn is None and connection_factory is None:
            raise ValueError("dsn or connection_factory is required")
        _quote(raw_schema)
        _quote(audit_schema)
        self.dsn = dsn
        self.connection_factory = connection_factory
        self.raw_schema = raw_schema
        self.audit_schema = audit_schema
        self.allow_schema_evolution = allow_schema_evolution
        self.fail_on_schema_drift = fail_on_schema_drift

    def _connect(self) -> Any:
        if self.connection_factory is not None:
            return self.connection_factory()
        try:
            import psycopg
        except ImportError as exc:
            raise PeoplePulseError(
                ErrorCode.DATABASE_UNAVAILABLE,
                "PostgreSQL loading requires the optional psycopg package.",
                cause=exc,
            ) from exc
        if self.dsn is None:
            raise AssertionError("dsn is required without a connection factory")
        return psycopg.connect(self.dsn)

    def _initialize(self, cursor: Any) -> None:
        raw = _quote(self.raw_schema)
        audit = _quote(self.audit_schema)
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {raw}")
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {audit}")
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {audit}.pipeline_batch (
                batch_id UUID PRIMARY KEY,
                pipeline_name TEXT NOT NULL,
                source_name TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                started_at TIMESTAMPTZ NOT NULL,
                completed_at TIMESTAMPTZ,
                status TEXT NOT NULL,
                extracted_count BIGINT NOT NULL DEFAULT 0,
                loaded_count BIGINT NOT NULL DEFAULT 0,
                rejected_count BIGINT NOT NULL DEFAULT 0,
                duplicate_count BIGINT NOT NULL DEFAULT 0,
                checksum TEXT NOT NULL DEFAULT '',
                checkpoint_value TEXT,
                error_code TEXT,
                error_message TEXT
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {audit}.ingestion_record_keys (
                source_name TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                record_hash TEXT NOT NULL,
                first_batch_id TEXT NOT NULL,
                first_loaded_at TIMESTAMPTZ NOT NULL,
                PRIMARY KEY (source_name, entity_name, record_hash)
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {audit}.dead_letter_record (
                rejection_id UUID PRIMARY KEY,
                batch_id UUID NOT NULL REFERENCES {audit}.pipeline_batch(batch_id),
                source_identifier TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                payload_encrypted_or_redacted JSONB NOT NULL,
                validation_error TEXT NOT NULL,
                rejected_at TIMESTAMPTZ NOT NULL,
                reprocessing_status TEXT NOT NULL DEFAULT 'pending'
            )
            """
        )
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {audit}.schema_drift_events (
                drift_id TEXT PRIMARY KEY,
                batch_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                drift_json JSONB NOT NULL,
                detected_at TIMESTAMPTZ NOT NULL
            )
            """
        )

    def _ensure_entity_table(
        self,
        cursor: Any,
        schema: SourceSchema,
        extras: Iterable[str],
    ) -> None:
        definitions = [
            f"{_quote(field.name)} {_postgres_type(field.data_type)}" for field in schema.fields
        ]
        definitions.extend(('"_ingested_at" TIMESTAMPTZ NOT NULL', '"_batch_id" TEXT NOT NULL'))
        qualified = f"{_quote(self.raw_schema)}.{_quote(schema.entity_name)}"
        cursor.execute(f"CREATE TABLE IF NOT EXISTS {qualified} ({', '.join(definitions)})")
        if self.allow_schema_evolution:
            for field_name in sorted(extras):
                cursor.execute(
                    f"ALTER TABLE {qualified} ADD COLUMN IF NOT EXISTS {_quote(field_name)} TEXT"
                )

    def _upsert_metadata(self, cursor: Any, item: BatchMetadata) -> None:
        cursor.execute(
            f"""
            INSERT INTO {_quote(self.audit_schema)}.pipeline_batch (
                batch_id, pipeline_name, source_name, entity_name,
                started_at, completed_at, status, extracted_count,
                loaded_count, rejected_count, duplicate_count, checksum,
                checkpoint_value, error_code, error_message
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
            ON CONFLICT (batch_id) DO UPDATE SET
                completed_at = EXCLUDED.completed_at,
                status = EXCLUDED.status,
                extracted_count = EXCLUDED.extracted_count,
                loaded_count = EXCLUDED.loaded_count,
                rejected_count = EXCLUDED.rejected_count,
                duplicate_count = EXCLUDED.duplicate_count,
                checksum = EXCLUDED.checksum,
                checkpoint_value = EXCLUDED.checkpoint_value,
                error_code = EXCLUDED.error_code,
                error_message = EXCLUDED.error_message
            """,
            (
                item.batch_id,
                item.pipeline_name,
                item.source_name,
                item.entity_name,
                item.started_at,
                item.completed_at,
                (
                    "completed_with_warnings"
                    if item.status == BatchStatus.COMPLETED_WITH_REJECTIONS
                    else item.status.value
                ),
                item.extracted_count,
                item.loaded_count,
                item.rejected_count,
                item.duplicate_count,
                item.checksum,
                item.checkpoint_value,
                item.error_code,
                item.error_message,
            ),
        )

    @staticmethod
    def _source_identifier(
        record: Mapping[str, Any],
        schema: SourceSchema,
    ) -> str:
        keys = tuple(str(record.get(key) or "") for key in schema.business_key)
        return "|".join(keys) if keys and all(keys) else f"hash:{record_hash(record)[:16]}"

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
        drift = (
            SchemaDriftDetector().detect(
                schema,
                infer_schema(schema.entity_name, materialized),
            )
            if materialized
            else SchemaDrift()
        )
        extra_fields = set(drift.added_fields)
        validator = validator or RecordValidator(
            schema,
            reject_unknown_fields=self.fail_on_schema_drift,
        )
        connection = self._connect()
        cursor = connection.cursor()
        try:
            self._initialize(cursor)
            self._ensure_entity_table(cursor, schema, extra_fields)
            self._upsert_metadata(cursor, metadata)
            if drift.detected:
                cursor.execute(
                    f"""
                    INSERT INTO {_quote(self.audit_schema)}.schema_drift_events (
                        drift_id, batch_id, source_name, entity_name,
                        drift_json, detected_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    """,
                    (
                        str(uuid4()),
                        context.batch_id,
                        context.source_name,
                        context.entity_name,
                        json.dumps(
                            {
                                "added_fields": drift.added_fields,
                                "missing_fields": drift.missing_fields,
                                "type_changes": drift.type_changes,
                            },
                            sort_keys=True,
                        ),
                        utc_now(),
                    ),
                )
            for record in materialized:
                validation = validator.validate(record)
                if not validation.valid:
                    errors = "; ".join(f"{issue.field}:{issue.code}" for issue in validation.issues)
                    dead_letter = DeadLetterRecord(
                        dead_letter_id=str(uuid4()),
                        payload=record,
                        source_identifier=self._source_identifier(record, schema),
                        validation_error=errors,
                        batch_id=context.batch_id,
                    )
                    dead_letters.append(dead_letter)
                    cursor.execute(
                        f"""
                        INSERT INTO {_quote(self.audit_schema)}.dead_letter_record (
                            rejection_id, batch_id, source_identifier,
                            entity_name, payload_encrypted_or_redacted,
                            validation_error, rejected_at, reprocessing_status
                        ) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                        """,
                        (
                            dead_letter.dead_letter_id,
                            dead_letter.batch_id,
                            dead_letter.source_identifier,
                            context.entity_name,
                            canonical_json(record),
                            dead_letter.validation_error,
                            dead_letter.rejected_at,
                            dead_letter.reprocessing_status,
                        ),
                    )
                    metadata.rejected_count += 1
                    continue
                item_hash = record_hash(record)
                cursor.execute(
                    f"""
                    INSERT INTO {_quote(self.audit_schema)}.ingestion_record_keys (
                        source_name, entity_name, record_hash,
                        first_batch_id, first_loaded_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING record_hash
                    """,
                    (
                        context.source_name,
                        context.entity_name,
                        item_hash,
                        context.batch_id,
                        utc_now(),
                    ),
                )
                if cursor.fetchone() is None:
                    metadata.duplicate_count += 1
                    continue
                columns = list(schema.field_names)
                if self.allow_schema_evolution:
                    columns.extend(sorted(extra_fields & set(record)))
                columns.extend(("_ingested_at", "_batch_id"))
                values = [
                    None if record.get(name) == "" else record.get(name) for name in columns[:-2]
                ]
                values.extend((utc_now(), context.batch_id))
                cursor.execute(
                    f"INSERT INTO {_quote(self.raw_schema)}.{_quote(schema.entity_name)} "
                    f"({', '.join(_quote(name) for name in columns)}) "
                    f"VALUES ({', '.join('%s' for _ in values)})",
                    values,
                )
                metadata.loaded_count += 1
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
            self._upsert_metadata(cursor, metadata)
            connection.commit()
        except Exception as exc:
            connection.rollback()
            metadata.completed_at = utc_now()
            metadata.status = BatchStatus.FAILED
            metadata.error_code = ErrorCode.LOAD_FAILED.value
            metadata.error_message = "PostgreSQL raw batch transaction failed."
            try:
                self._initialize(cursor)
                self._upsert_metadata(cursor, metadata)
                connection.commit()
            except Exception:
                # The original load failure remains authoritative. A database
                # outage can also prevent recording failure metadata.
                connection.rollback()
            raise PeoplePulseError(
                ErrorCode.LOAD_FAILED,
                "PostgreSQL raw batch transaction failed.",
                retryable=True,
                context={
                    "batch_id": context.batch_id,
                    "source": context.source_name,
                    "entity": context.entity_name,
                },
                cause=exc,
            ) from exc
        finally:
            cursor.close()
            connection.close()
        return LoadResult(
            metadata=metadata,
            dead_letters=tuple(dead_letters),
            reconciliation=reconciliation,
        )
