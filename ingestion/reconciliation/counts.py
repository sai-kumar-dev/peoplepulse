"""Count and key reconciliation without exposing record payloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from peoplepulse.common.models import ReconciliationResult


def reconcile_counts(
    extracted_count: int,
    loaded_count: int,
    rejected_count: int = 0,
    duplicate_count: int = 0,
) -> ReconciliationResult:
    accounted = loaded_count + rejected_count + duplicate_count
    difference = extracted_count - accounted
    matched = difference == 0
    message = (
        "Source records fully accounted for."
        if matched
        else f"{abs(difference)} record(s) are not reconciled."
    )
    return ReconciliationResult(
        matched=matched,
        extracted_count=extracted_count,
        accounted_count=accounted,
        difference=difference,
        message=message,
    )


@dataclass(frozen=True, slots=True)
class RecordReconciliation:
    matched: bool
    source_count: int
    target_count: int
    missing_keys: tuple[tuple[Any, ...], ...]
    unexpected_keys: tuple[tuple[Any, ...], ...]


def reconcile_records(
    source_records: Iterable[Mapping[str, Any]],
    target_records: Iterable[Mapping[str, Any]],
    key_fields: Sequence[str],
) -> RecordReconciliation:
    if not key_fields:
        raise ValueError("key_fields cannot be empty")

    def keys(records: Iterable[Mapping[str, Any]]) -> set[tuple[Any, ...]]:
        return {tuple(record.get(field_name) for field_name in key_fields) for record in records}

    source_keys = keys(source_records)
    target_keys = keys(target_records)
    missing = tuple(sorted(source_keys - target_keys, key=repr))
    unexpected = tuple(sorted(target_keys - source_keys, key=repr))
    return RecordReconciliation(
        matched=not missing and not unexpected,
        source_count=len(source_keys),
        target_count=len(target_keys),
        missing_keys=missing,
        unexpected_keys=unexpected,
    )
