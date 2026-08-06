"""Connector protocol shared by file, database, and API sources."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from peoplepulse.common.models import (
    Checkpoint,
    ExtractionContext,
    Record,
    SourceSchema,
)


@runtime_checkable
class SourceConnector(Protocol):
    def extract(self, context: ExtractionContext) -> Iterable[Record]: ...

    def get_schema(self) -> SourceSchema: ...

    def get_checkpoint(self) -> Checkpoint | None: ...

    def commit_checkpoint(self, checkpoint: Checkpoint) -> None: ...
