"""Run the initial vertical-slice checks against generated CSV files."""

from __future__ import annotations

import argparse
import csv
import os
from collections.abc import Sequence
from pathlib import Path

from peoplepulse.quality.checks import (
    check_employment_dates,
    check_not_null,
    check_references,
    check_unique,
)
from peoplepulse.quality.runner import QualityGateError, QualityRunner


def _records(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path(os.getenv("PEOPLEPULSE_DATA_DIR", "data/generated")),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/data_quality/latest.json"),
    )
    parser.add_argument(
        "--allow-critical",
        action="store_true",
        help="Persist critical failures without returning a failing exit code.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    employees = _records(args.input_dir / "employees.csv")
    departments = _records(args.input_dir / "departments.csv")
    department_keys = [record["department_id"] for record in departments]
    results = [
        check_not_null(employees, entity="employees", field="employee_id"),
        check_unique(employees, entity="employees", field="employee_id"),
        check_references(
            employees,
            entity="employees",
            foreign_key="department_id",
            valid_keys=department_keys,
        ),
        check_employment_dates(employees),
    ]
    try:
        QualityRunner(args.output).evaluate(
            results,
            fail_on_critical=not args.allow_critical,
        )
    except QualityGateError as exc:
        print(str(exc))
        return 1
    print(f"Quality results written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
