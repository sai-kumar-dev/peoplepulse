"""Source schema inference and evolution detection."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import date, datetime
from decimal import Decimal
from typing import Any, ClassVar

from peoplepulse.common.models import FieldSpec, SchemaDrift, SourceSchema


def infer_value_type(value: Any) -> str:
    if value is None or value == "":
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, (float, Decimal)):
        return "number"
    if isinstance(value, datetime):
        return "datetime"
    if isinstance(value, date):
        return "date"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, (list, tuple)):
        return "array"
    return "string"


def infer_schema(
    entity_name: str,
    records: Iterable[Mapping[str, Any]],
) -> SourceSchema:
    """Infer a conservative schema from records without consuming dependencies."""
    observed: dict[str, set[str]] = {}
    nullable: set[str] = set()
    record_count = 0
    for record in records:
        record_count += 1
        for known_name in set(observed) - set(record):
            nullable.add(known_name)
        for name, value in record.items():
            value_type = infer_value_type(value)
            if value_type == "null":
                nullable.add(name)
            else:
                observed.setdefault(name, set()).add(value_type)
        for new_name in set(record) - set(observed):
            observed[new_name] = set()
    fields: list[FieldSpec] = []
    for name in sorted(observed):
        types = observed[name]
        if not types:
            data_type = "string"
        elif len(types) == 1:
            data_type = next(iter(types))
        elif types <= {"integer", "number"}:
            data_type = "number"
        else:
            data_type = "mixed"
        fields.append(
            FieldSpec(
                name=name,
                data_type=data_type,
                nullable=name in nullable or record_count == 0,
            )
        )
    return SourceSchema(entity_name=entity_name, fields=tuple(fields))


class SchemaDriftDetector:
    """Compare source contracts and report actionable structural drift."""

    _COMPATIBLE: ClassVar[frozenset[tuple[str, str]]] = frozenset(
        {
            ("integer", "number"),
            ("date", "string"),
            ("datetime", "string"),
            ("boolean", "string"),
            ("integer", "string"),
            ("number", "string"),
        }
    )

    def __init__(self, *, allow_serialized_strings: bool = True) -> None:
        self.allow_serialized_strings = allow_serialized_strings

    def detect(
        self,
        expected: SourceSchema,
        observed: SourceSchema,
    ) -> SchemaDrift:
        expected_fields = expected.field_map
        observed_fields = observed.field_map
        added = tuple(sorted(set(observed_fields) - set(expected_fields)))
        missing = tuple(sorted(set(expected_fields) - set(observed_fields)))
        type_changes: dict[str, tuple[str, str]] = {}
        for name in sorted(set(expected_fields) & set(observed_fields)):
            expected_type = expected_fields[name].data_type
            observed_type = observed_fields[name].data_type
            if observed_type in {"null", "mixed"}:
                if observed_type == "mixed":
                    type_changes[name] = (expected_type, observed_type)
                continue
            compatible = expected_type == observed_type
            if self.allow_serialized_strings:
                compatible = (
                    compatible
                    or (
                        expected_type,
                        observed_type,
                    )
                    in self._COMPATIBLE
                )
            if not compatible:
                type_changes[name] = (expected_type, observed_type)
        return SchemaDrift(
            added_fields=added,
            missing_fields=missing,
            type_changes=type_changes,
        )
