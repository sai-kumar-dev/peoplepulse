"""Deterministic problematic-data scenarios used in demos and tests."""

from __future__ import annotations

import random
from collections.abc import Iterable
from datetime import date, timedelta

from data_generator.models import GeneratedDataset

SUPPORTED_SCENARIOS = frozenset(
    {
        "normal",
        "rapid_hiring",
        "hiring_freeze",
        "increased_attrition",
        "bad_record",
        "deliberate_bad_record",
        "duplicate_source_records",
        "missing_department",
        "invalid_dates",
        "future_hire_dates",
        "termination_before_hire_date",
        "null_business_key",
        "schema_drift",
        "out_of_order_records",
        "repeated_ingestion_batch",
    }
)


def apply_scenarios(
    dataset: GeneratedDataset,
    *,
    scenarios: Iterable[str],
    rng: random.Random,
    as_of_date: date,
) -> None:
    """Mutate a generated dataset with explicitly requested data conditions."""
    normalized = tuple(dict.fromkeys(item.lower() for item in scenarios))
    unknown = sorted(set(normalized) - SUPPORTED_SCENARIOS)
    if unknown:
        raise ValueError(f"unsupported scenario(s): {', '.join(unknown)}")

    for scenario in normalized:
        if scenario in {
            "normal",
            "rapid_hiring",
            "hiring_freeze",
            "increased_attrition",
        }:
            continue
        if scenario in {"bad_record", "deliberate_bad_record"}:
            bad = dataset.employees[-1]
            bad["employee_id"] = ""
            bad["department_id"] = "DEP-MISSING"
            bad["hire_date"] = "not-a-date"
        elif scenario == "duplicate_source_records":
            dataset.employees.append(dict(dataset.employees[0]))
            dataset.hires.append(dict(dataset.hires[0]))
        elif scenario == "missing_department":
            dataset.employees[-1]["department_id"] = "DEP-MISSING"
        elif scenario == "invalid_dates":
            dataset.employees[-1]["hire_date"] = "31/31/2025"
        elif scenario == "future_hire_dates":
            future = (as_of_date + timedelta(days=60)).isoformat()
            dataset.employees[-1]["hire_date"] = future
            dataset.hires[-1]["hire_date"] = future
        elif scenario == "termination_before_hire_date":
            employee = dataset.employees[-1]
            hire = date.fromisoformat(str(employee["hire_date"]))
            employee["termination_date"] = (hire - timedelta(days=1)).isoformat()
            employee["employment_status"] = "terminated"
        elif scenario == "null_business_key":
            dataset.employees[-1]["employee_id"] = None
        elif scenario == "schema_drift":
            dataset.employees[0]["unexpected_hr_code"] = "NEW-COLUMN"
        elif scenario == "out_of_order_records":
            rng.shuffle(dataset.employees)
            rng.shuffle(dataset.hires)
            rng.shuffle(dataset.terminations)
        elif scenario == "repeated_ingestion_batch":
            dataset.employees.extend(dict(item) for item in dataset.employees)
            dataset.hires.extend(dict(item) for item in dataset.hires)


__all__ = ["SUPPORTED_SCENARIOS", "apply_scenarios"]
