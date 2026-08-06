"""JSON array, envelope, and newline-delimited JSON source connector."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from ingestion.checkpoints import CheckpointStore
from ingestion.connectors.file_base import FileConnectorBase
from ingestion.validation import infer_schema
from peoplepulse.common.errors import ErrorCode, PeoplePulseError
from peoplepulse.common.models import (
    Checkpoint,
    ExtractionContext,
    Record,
    SourceSchema,
    utc_now,
)


class JSONConnector(FileConnectorBase):
    def __init__(
        self,
        path: str | Path,
        *,
        entity_name: str | None = None,
        source_name: str = "json",
        schema: SourceSchema | None = None,
        checkpoint_store: CheckpointStore | None = None,
        records_key: str = "records",
        encoding: str = "utf-8",
    ) -> None:
        self.path = Path(path)
        inferred_entity = entity_name or self.path.stem
        super().__init__(
            source_name=source_name,
            entity_name=inferred_entity,
            checkpoint_store=checkpoint_store,
        )
        self._schema = schema
        self.records_key = records_key
        self.encoding = encoding

    def _ensure_available(self) -> None:
        if not self.path.is_file():
            raise PeoplePulseError(
                ErrorCode.SOURCE_UNAVAILABLE,
                "JSON source file is unavailable.",
                retryable=True,
                context={
                    "source": self.source_name,
                    "entity": self.entity_name,
                    "path": str(self.path),
                },
            )

    def _records(self) -> list[dict[str, Any]]:
        self._ensure_available()
        try:
            text = self.path.read_text(encoding=self.encoding)
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                value = [json.loads(line) for line in text.splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError) as exc:
            raise PeoplePulseError(
                ErrorCode.EXTRACTION_FAILED,
                "JSON source could not be decoded.",
                context={"source": self.source_name, "entity": self.entity_name},
                cause=exc,
            ) from exc
        if isinstance(value, dict):
            value = value.get(self.records_key)
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise PeoplePulseError(
                ErrorCode.SOURCE_SCHEMA_INVALID,
                "JSON source must be an array of objects or a records envelope.",
                context={"source": self.source_name, "entity": self.entity_name},
            )
        return [dict(item) for item in value]

    def get_schema(self) -> SourceSchema:
        return self._schema or infer_schema(self.entity_name, self._records())

    def extract(self, context: ExtractionContext) -> Iterable[Record]:
        records = self._records()
        offset = self._starting_offset(context.since)
        remaining = records[offset:]
        if context.limit is not None:
            remaining = remaining[: context.limit]
        yield from remaining
        self.proposed_checkpoint = Checkpoint(
            source_name=self.source_name,
            entity_name=self.entity_name,
            value=offset + len(remaining),
            updated_at=utc_now(),
        )
