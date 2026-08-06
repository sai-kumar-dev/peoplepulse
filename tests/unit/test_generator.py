from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from data_generator import GenerationConfig, generate_dataset
from data_generator.generate import write_dataset
from data_generator.schemas import EMPLOYEE_SCHEMA, PII_FIELDS, SCHEMAS
from ingestion.validation import RecordValidator, SchemaDriftDetector, infer_schema


def test_generator_is_deterministic_and_referentially_consistent() -> None:
    config = GenerationConfig(
        employees=80,
        months=24,
        scenario="normal",
        seed=42,
        as_of_date=date(2025, 1, 31),
    )

    first = generate_dataset(config)
    second = generate_dataset(config)

    assert first.entities() == second.entities()
    assert len(first.employees) == 80
    assert len(first.hires) == 80
    assert first.terminations
    department_ids = {item["department_id"] for item in first.departments}
    employee_ids = {item["employee_id"] for item in first.employees}
    assert all(item["department_id"] in department_ids for item in first.employees)
    assert all(item["employee_id"] in employee_ids for item in first.hires)
    assert all(item["employee_id"] in employee_ids for item in first.terminations)
    assert all(
        not item["termination_date"] or item["termination_date"] >= item["hire_date"]
        for item in first.employees
    )


def test_scenarios_produce_bad_record_and_detectable_schema_drift() -> None:
    bad = generate_dataset(
        employees=10,
        months=12,
        scenario="deliberate_bad_record",
        seed=7,
    )
    validation = RecordValidator(EMPLOYEE_SCHEMA).validate(bad.employees[-1])
    assert not validation.valid
    assert {issue.code for issue in validation.issues} >= {
        "REQUIRED",
        "INVALID_TYPE",
    }

    drifted = generate_dataset(
        employees=10,
        months=12,
        scenario="schema_drift",
        seed=7,
    )
    observed = infer_schema("employees", drifted.employees)
    drift = SchemaDriftDetector().detect(EMPLOYEE_SCHEMA, observed)
    assert drift.detected
    assert drift.added_fields == ("unexpected_hr_code",)


def test_generator_writes_matching_csv_json_and_manifest(tmp_path: Path) -> None:
    config = GenerationConfig(employees=15, months=6, seed=11)
    result = write_dataset(tmp_path, config=config)

    assert len(result.files) == 9
    assert result.counts["employees"] == 15
    for entity_name, schema in SCHEMAS.items():
        csv_path = tmp_path / f"{entity_name}.csv"
        json_path = tmp_path / f"{entity_name}.json"
        assert csv_path.is_file()
        assert json_path.is_file()
        with csv_path.open(encoding="utf-8", newline="") as handle:
            csv_records = list(csv.DictReader(handle))
        json_records = json.loads(json_path.read_text(encoding="utf-8"))
        assert len(csv_records) == len(json_records) == result.counts[entity_name]
        assert set(schema.field_names) <= set(csv_records[0] if csv_records else schema.field_names)

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["seed"] == 11
    assert manifest["counts"] == result.counts
    assert set(PII_FIELDS) >= {"first_name", "last_name", "email", "phone"}


def test_attrition_scenario_increases_termination_volume() -> None:
    normal = generate_dataset(
        employees=500,
        months=24,
        scenario="normal",
        seed=22,
    )
    increased = generate_dataset(
        employees=500,
        months=24,
        scenario="increased_attrition",
        seed=22,
    )

    assert len(increased.terminations) > len(normal.terminations)
