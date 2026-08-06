"""Canonical serialization and hashes for idempotent data handling."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (Decimal, UUID)):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"Unsupported value for canonical JSON: {type(value).__name__}")


def canonical_json(record: Mapping[str, Any]) -> str:
    """Serialize a record consistently across platforms and source formats."""
    return json.dumps(
        dict(record),
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def record_hash(record: Mapping[str, Any]) -> str:
    """Return a SHA-256 content hash for one source record."""
    return hashlib.sha256(canonical_json(record).encode("utf-8")).hexdigest()


def checksum_records(records: Iterable[Mapping[str, Any]]) -> str:
    """Return an order-independent checksum for a batch of records."""
    digest = hashlib.sha256()
    for item_hash in sorted(record_hash(record) for record in records):
        digest.update(item_hash.encode("ascii"))
    return digest.hexdigest()
