"""Incremental PostgreSQL connector with an injectable DB-API connection."""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

from ingestion.checkpoints import CheckpointStore, InMemoryCheckpointStore
from ingestion.validation import infer_schema
from peoplepulse.common.errors import ErrorCode, PeoplePulseError
from peoplepulse.common.models import (
    Checkpoint,
    ExtractionContext,
    Record,
    SourceSchema,
    utc_now,
)

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"unsafe SQL identifier: {value!r}")
    return f'"{value}"'


class PostgreSQLConnector:
    """Read a source table using server-side filtering where configured."""

    def __init__(
        self,
        table: str,
        *,
        entity_name: str | None = None,
        schema_name: str = "public",
        source_name: str = "postgresql",
        dsn: str | None = None,
        connection_factory: Callable[[], Any] | None = None,
        schema: SourceSchema | None = None,
        checkpoint_column: str | None = None,
        checkpoint_store: CheckpointStore | None = None,
        placeholder: str = "%s",
    ) -> None:
        _identifier(table)
        _identifier(schema_name)
        if checkpoint_column is not None:
            _identifier(checkpoint_column)
        if dsn is None and connection_factory is None:
            raise ValueError("dsn or connection_factory is required")
        self.table = table
        self.schema_name = schema_name
        self.entity_name = entity_name or table
        self.source_name = source_name
        self.dsn = dsn
        self.connection_factory = connection_factory
        self._schema = schema
        self.checkpoint_column = checkpoint_column
        self.checkpoint_store = checkpoint_store or InMemoryCheckpointStore()
        self.placeholder = placeholder
        self.proposed_checkpoint: Checkpoint | None = None

    @property
    def qualified_table(self) -> str:
        return f"{_identifier(self.schema_name)}.{_identifier(self.table)}"

    def _connect(self) -> tuple[Any, bool]:
        if self.connection_factory is not None:
            return self.connection_factory(), True
        try:
            import psycopg
        except ImportError as exc:
            raise PeoplePulseError(
                ErrorCode.DATABASE_UNAVAILABLE,
                "PostgreSQL support requires the optional psycopg package.",
                cause=exc,
            ) from exc
        try:
            if self.dsn is None:
                raise AssertionError("dsn is required without a connection factory")
            return psycopg.connect(self.dsn), True
        except Exception as exc:
            raise PeoplePulseError(
                ErrorCode.SOURCE_UNAVAILABLE,
                "PostgreSQL source is unavailable.",
                retryable=True,
                context={"source": self.source_name, "entity": self.entity_name},
                cause=exc,
            ) from exc

    def get_checkpoint(self) -> Checkpoint | None:
        return self.checkpoint_store.get(self.source_name, self.entity_name)

    def commit_checkpoint(self, checkpoint: Checkpoint) -> None:
        if checkpoint.source_name != self.source_name or checkpoint.entity_name != self.entity_name:
            raise ValueError("checkpoint source/entity does not match connector")
        self.checkpoint_store.commit(checkpoint)

    def get_schema(self) -> SourceSchema:
        if self._schema is not None:
            return self._schema
        connection, should_close = self._connect()
        try:
            cursor = connection.cursor()
            try:
                cursor.execute(f"SELECT * FROM {self.qualified_table} LIMIT 1")
                names = [item[0] for item in cursor.description or ()]
                row = cursor.fetchone()
            finally:
                cursor.close()
        except Exception as exc:
            raise PeoplePulseError(
                ErrorCode.SOURCE_SCHEMA_INVALID,
                "PostgreSQL source schema could not be inspected.",
                context={"source": self.source_name, "entity": self.entity_name},
                cause=exc,
            ) from exc
        finally:
            if should_close:
                connection.close()
        record = dict(zip(names, row, strict=True)) if row is not None else dict.fromkeys(names)
        return infer_schema(self.entity_name, (record,))

    def extract(self, context: ExtractionContext) -> Iterable[Record]:
        connection, should_close = self._connect()
        cursor = connection.cursor()
        query = f"SELECT * FROM {self.qualified_table}"
        parameters: list[Any] = []
        current = context.since
        if current is None:
            checkpoint = self.get_checkpoint()
            current = checkpoint.value if checkpoint else None
        if self.checkpoint_column is not None and current is not None:
            query += f" WHERE {_identifier(self.checkpoint_column)} > {self.placeholder}"
            parameters.append(current)
        if self.checkpoint_column is not None:
            query += f" ORDER BY {_identifier(self.checkpoint_column)}"
        if context.limit is not None:
            query += f" LIMIT {self.placeholder}"
            parameters.append(context.limit)
        last_checkpoint = current
        try:
            cursor.execute(query, tuple(parameters))
            names = [item[0] for item in cursor.description or ()]
            for row in cursor:
                record = dict(zip(names, row, strict=True))
                if self.checkpoint_column is not None:
                    last_checkpoint = record[self.checkpoint_column]
                yield record
        except Exception as exc:
            raise PeoplePulseError(
                ErrorCode.EXTRACTION_FAILED,
                "PostgreSQL extraction failed.",
                retryable=True,
                context={"source": self.source_name, "entity": self.entity_name},
                cause=exc,
            ) from exc
        finally:
            cursor.close()
            if should_close:
                connection.close()
        if self.checkpoint_column is not None and last_checkpoint is not None:
            self.proposed_checkpoint = Checkpoint(
                source_name=self.source_name,
                entity_name=self.entity_name,
                value=last_checkpoint,
                updated_at=utc_now(),
            )
