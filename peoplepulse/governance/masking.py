"""Central policy for employee-field classification and masking."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class Classification(StrEnum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED_PII = "restricted_pii"


class AccessRole(StrEnum):
    EXECUTIVE = "executive"
    ANALYST = "analyst"
    HR_RESTRICTED = "hr_restricted"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class FieldPolicy:
    classification: Classification
    visible_to: frozenset[AccessRole]
    mask: str = "redact"


FIELD_POLICIES: dict[str, FieldPolicy] = {
    "employee_id": FieldPolicy(
        Classification.CONFIDENTIAL,
        frozenset({AccessRole.HR_RESTRICTED, AccessRole.ADMIN}),
        "tokenize",
    ),
    "first_name": FieldPolicy(
        Classification.RESTRICTED_PII,
        frozenset({AccessRole.HR_RESTRICTED, AccessRole.ADMIN}),
    ),
    "last_name": FieldPolicy(
        Classification.RESTRICTED_PII,
        frozenset({AccessRole.HR_RESTRICTED, AccessRole.ADMIN}),
    ),
    "preferred_name": FieldPolicy(
        Classification.RESTRICTED_PII,
        frozenset({AccessRole.HR_RESTRICTED, AccessRole.ADMIN}),
    ),
    "email": FieldPolicy(
        Classification.RESTRICTED_PII,
        frozenset({AccessRole.HR_RESTRICTED, AccessRole.ADMIN}),
        "email",
    ),
    "phone": FieldPolicy(
        Classification.RESTRICTED_PII,
        frozenset({AccessRole.HR_RESTRICTED, AccessRole.ADMIN}),
    ),
    "date_of_birth": FieldPolicy(
        Classification.RESTRICTED_PII,
        frozenset({AccessRole.HR_RESTRICTED, AccessRole.ADMIN}),
    ),
    "base_salary": FieldPolicy(
        Classification.CONFIDENTIAL,
        frozenset({AccessRole.HR_RESTRICTED, AccessRole.ADMIN}),
        "numeric",
    ),
}


def _masked(value: Any, strategy: str) -> str | None:
    if value is None:
        return None
    if strategy == "email":
        text = str(value)
        _, separator, domain = text.rpartition("@")
        return f"***@{domain}" if separator and domain else "***"
    if strategy == "tokenize":
        digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]
        return f"person_{digest}"
    if strategy == "numeric":
        return "[restricted]"
    return "***"


def mask_record(record: Mapping[str, Any], *, role: AccessRole) -> dict[str, Any]:
    """Return a copy with protected values masked for the caller's role."""
    output: dict[str, Any] = {}
    for field, value in record.items():
        policy = FIELD_POLICIES.get(field)
        if policy is None or role in policy.visible_to:
            output[field] = value
        else:
            output[field] = _masked(value, policy.mask)
    return output
