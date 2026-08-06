"""Streaming CSV source connector."""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path

from ingestion.checkpoints import CheckpointStore
from ingestion.connectors.file_base import FileConnectorBase
from peoplepulse.common.errors import ErrorCode, PeoplePulseError
from peoplepulse.common.models import (
    Checkpoint,
    ExtractionContext,
    FieldSpec,
    Record,
    SourceSchema,
    utc_now,
)


class CSVConnector(FileConnectorBase):
    def __init__(
        self,
        path: str | Path,
        *,
        entity_name: str | None = None,
        source_name: str = "csv",
        schema: SourceSchema | None = None,
        checkpoint_store: CheckpointStore | None = None,
        encoding: str = "utf-8-sig",
        delimiter: str = ",",
    ) -> None:
        self.path = Path(path)
        inferred_entity = entity_name or self.path.stem
        super().__init__(
            source_name=source_name,
            entity_name=inferred_entity,
            checkpoint_store=checkpoint_store,
        )
        self._schema = schema
        self.encoding = encoding
        self.delimiter = delimiter

    def _ensure_available(self) -> None:
        if not self.path.is_file():
            raise PeoplePulseError(
                ErrorCode.SOURCE_UNAVAILABLE,
                "CSV source file is unavailable.",
                retryable=True,
                context={
                    "source": self.source_name,
                    "entity": self.entity_name,
                    "path": str(self.path),
                },
            )

    def get_schema(self) -> SourceSchema:
        if self._schema is not None:
            return self._schema
        self._ensure_available()
        try:
            with self.path.open(
                "r",
                encoding=self.encoding,
                newline="",
            ) as handle:
                reader = csv.reader(handle, delimiter=self.delimiter)
                header = next(reader)
        except (OSError, csv.Error, StopIteration) as exc:
            raise PeoplePulseError(
                ErrorCode.SOURCE_SCHEMA_INVALID,
                "CSV header could not be read.",
                context={"source": self.source_name, "entity": self.entity_name},
                cause=exc,
            ) from exc
        if not header or any(not value.strip() for value in header):
            raise PeoplePulseError(
                ErrorCode.SOURCE_SCHEMA_INVALID,
                "CSV header contains an empty field name.",
                context={"source": self.source_name, "entity": self.entity_name},
            )
        if len(set(header)) != len(header):
            raise PeoplePulseError(
                ErrorCode.SOURCE_SCHEMA_INVALID,
                "CSV header contains duplicate field names.",
                context={"source": self.source_name, "entity": self.entity_name},
            )
        return SourceSchema(
            entity_name=self.entity_name,
            fields=tuple(FieldSpec(name=name) for name in header),
        )

    def extract(self, context: ExtractionContext) -> Iterable[Record]:
        self._ensure_available()
        offset = self._starting_offset(context.since)
        emitted = 0
        last_offset = offset
        try:
            with self.path.open(
                "r",
                encoding=self.encoding,
                newline="",
            ) as handle:
                reader = csv.DictReader(handle, delimiter=self.delimiter)
                if reader.fieldnames is None:
                    raise PeoplePulseError(
                        ErrorCode.SOURCE_SCHEMA_INVALID,
                        "CSV source does not contain a header.",
                    )
                for row_number, row in enumerate(reader, start=1):
                    if row_number <= offset:
                        continue
                    if None in row:
                        raise PeoplePulseError(
                            ErrorCode.SOURCE_SCHEMA_INVALID,
                            "CSV row contains more values than its header.",
                            context={
                                "source": self.source_name,
                                "entity": self.entity_name,
                                "row_number": row_number,
                            },
                        )
                    yield dict(row)
                    emitted += 1
                    last_offset = row_number
                    if context.limit is not None and emitted >= context.limit:
                        break
        except OSError as exc:
            raise PeoplePulseError(
                ErrorCode.EXTRACTION_FAILED,
                "CSV extraction failed.",
                retryable=True,
                context={"source": self.source_name, "entity": self.entity_name},
                cause=exc,
            ) from exc
        self.proposed_checkpoint = Checkpoint(
            source_name=self.source_name,
            entity_name=self.entity_name,
            value=last_offset,
            updated_at=utc_now(),
        )
