from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from data_generator import GenerationConfig, generate_dataset
from data_generator.generate import main, write_dataset


@pytest.mark.parametrize(
    ("employees", "months", "message"),
    [
        (0, 12, "employees"),
        (1, 0, "months"),
        (1, 601, "months"),
    ],
)
def test_generation_config_rejects_invalid_sizes(
    employees: int,
    months: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        GenerationConfig(employees=employees, months=months)


def test_generation_config_normalizes_scenario_lists() -> None:
    assert GenerationConfig(scenario=" , ").scenarios == ("normal",)
    assert GenerationConfig(scenario="NORMAL, schema_drift,normal").scenarios == (
        "normal",
        "schema_drift",
        "normal",
    )
    with pytest.raises(TypeError, match="either config or keyword"):
        generate_dataset(GenerationConfig(), employees=2)


@pytest.mark.parametrize(
    "scenario",
    [
        "rapid_hiring",
        "hiring_freeze",
        "increased_attrition",
        "duplicate_source_records",
        "missing_department",
        "invalid_dates",
        "future_hire_dates",
        "termination_before_hire_date",
        "null_business_key",
        "schema_drift",
        "out_of_order_records",
        "repeated_ingestion_batch",
    ],
)
def test_all_supported_scenarios_are_deterministic(scenario: str) -> None:
    first = generate_dataset(
        employees=24,
        months=18,
        scenario=scenario,
        seed=19,
    )
    second = generate_dataset(
        employees=24,
        months=18,
        scenario=scenario,
        seed=19,
    )
    assert first.entities() == second.entities()

    if scenario == "duplicate_source_records":
        assert len(first.employees) == 25
        assert first.employees[-1] == first.employees[0]
    elif scenario == "missing_department":
        assert first.employees[-1]["department_id"] == "DEP-MISSING"
    elif scenario == "invalid_dates":
        assert first.employees[-1]["hire_date"] == "31/31/2025"
    elif scenario == "future_hire_dates":
        assert first.employees[-1]["hire_date"] > "2025-01-31"
    elif scenario == "termination_before_hire_date":
        assert first.employees[-1]["termination_date"] < first.employees[-1]["hire_date"]
    elif scenario == "null_business_key":
        assert first.employees[-1]["employee_id"] is None
    elif scenario == "schema_drift":
        assert first.employees[0]["unexpected_hr_code"] == "NEW-COLUMN"
    elif scenario == "repeated_ingestion_batch":
        assert len(first.employees) == 48


def test_unknown_scenario_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported scenario"):
        generate_dataset(employees=5, scenario="alien_invasion")


def test_write_dataset_validates_formats_and_json_only_output(tmp_path: Path) -> None:
    config = GenerationConfig(employees=3, months=1, seed=2)
    result = write_dataset(tmp_path / "json", config=config, formats=("json", "json"))
    assert len(result.files) == 5
    assert not (result.output_dir / "employees.csv").exists()
    assert (result.output_dir / "employees.json").is_file()

    with pytest.raises(ValueError, match="unsupported output"):
        write_dataset(tmp_path / "bad", config=config, formats=("xml",))
    with pytest.raises(ValueError, match="at least one"):
        write_dataset(tmp_path / "empty", config=config, formats=())


def test_generator_cli_main_writes_requested_data(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    destination = tmp_path / "cli"
    exit_code = main(
        [
            "--employees",
            "7",
            "--months",
            "3",
            "--scenario",
            "schema_drift",
            "--seed",
            "17",
            "--as-of-date",
            date(2025, 2, 28).isoformat(),
            "--output-dir",
            str(destination),
            "--format",
            "json",
        ]
    )

    assert exit_code == 0
    assert "employees=7" in capsys.readouterr().out
    employees = json.loads((destination / "employees.json").read_text(encoding="utf-8"))
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert employees[0]["unexpected_hr_code"] == "NEW-COLUMN"
    assert manifest["config"]["as_of_date"] == "2025-02-28"
