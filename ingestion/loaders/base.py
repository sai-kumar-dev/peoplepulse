"""Loader protocol for connector-independent ingestion."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from ingestion.validation import RecordValidator
from peoplepulse.common.models import (
    LoadContext,
    LoadResult,
    Record,
    SourceSchema,
)


@runtime_checkable
class RawLoader(Protocol):
    def load(
        self,
        records: Iterable[Record],
        *,
        context: LoadContext,
        schema: SourceSchema,
        validator: RecordValidator | None = None,
    ) -> LoadResult: ...
