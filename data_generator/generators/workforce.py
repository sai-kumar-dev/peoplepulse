"""Deterministic generator for the HRIS workforce vertical slice."""

from __future__ import annotations

import calendar
import random
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from data_generator.models import GeneratedDataset, GenerationConfig
from data_generator.scenarios import apply_scenarios

_DEPARTMENTS = (
    ("Engineering", None),
    ("People", None),
    ("Finance", None),
    ("Sales", None),
    ("Operations", None),
    ("Data & Analytics", "Engineering"),
    ("Talent Acquisition", "People"),
    ("Customer Success", "Sales"),
)
_FIRST_NAMES = (
    "Aarav",
    "Aisha",
    "Ananya",
    "Arjun",
    "Diya",
    "Ishaan",
    "Kabir",
    "Kavya",
    "Maya",
    "Meera",
    "Neha",
    "Priya",
    "Rohan",
    "Sai",
    "Sanjay",
    "Tara",
    "Vikram",
    "Zoya",
)
_LAST_NAMES = (
    "Bose",
    "Chandra",
    "Das",
    "Gupta",
    "Iyer",
    "Joshi",
    "Kapoor",
    "Khan",
    "Kumar",
    "Mehta",
    "Nair",
    "Patel",
    "Rao",
    "Reddy",
    "Shah",
    "Singh",
)
_GENDERS = ("female", "male", "non_binary", "not_disclosed")
_LOCATIONS = ("LOC-BLR", "LOC-HYD", "LOC-LON", "LOC-NYC", "LOC-PUN")
_JOB_LEVELS = ("L1", "L2", "L3", "L4", "L5", "L6")
_WORK_ARRANGEMENTS = ("onsite", "hybrid", "remote")
_TERMINATION_REASONS = {
    "voluntary": ("career_change", "compensation", "relocation", "personal"),
    "involuntary": ("performance", "restructuring", "role_eliminated"),
}


def _subtract_months(value: date, months: int) -> date:
    month_index = value.year * 12 + value.month - 1 - months
    year, month_zero = divmod(month_index, 12)
    month = month_zero + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _timestamp(value: date, *, hour: int = 9) -> str:
    return datetime.combine(value, time(hour=hour), tzinfo=UTC).isoformat()


def _slug(value: str) -> str:
    return value.lower().replace("&", "and").replace(" ", ".").replace("'", "")


def _generate_departments(as_of_date: date) -> list[dict[str, Any]]:
    ids_by_name = {name: f"DEP{index:03d}" for index, (name, _) in enumerate(_DEPARTMENTS, start=1)}
    created = _timestamp(_subtract_months(as_of_date, 120))
    return [
        {
            "department_id": ids_by_name[name],
            "department_name": name,
            "parent_department_id": (ids_by_name[parent] if parent is not None else None),
            "cost_center_id": f"CC{index:03d}",
            "created_at": created,
            "updated_at": _timestamp(as_of_date),
            "source_system": "hris",
        }
        for index, (name, parent) in enumerate(_DEPARTMENTS, start=1)
    ]


def _hire_offset(
    rng: random.Random,
    config: GenerationConfig,
) -> int:
    scenarios = config.scenarios
    if "rapid_hiring" in scenarios:
        # Bias hires toward the latest quarter while preserving older history.
        return min(
            config.months * 30 - 1,
            int((rng.random() ** 2.5) * config.months * 30),
        )
    if "hiring_freeze" in scenarios:
        minimum = min(config.months * 30 - 1, 120)
        return rng.randint(minimum, max(minimum, config.months * 30 - 1))
    return rng.randint(0, config.months * 30 - 1)


def _termination_probability(config: GenerationConfig) -> float:
    if "increased_attrition" in config.scenarios:
        return 0.30
    if "rapid_hiring" in config.scenarios:
        return 0.05
    return 0.11


def _termination_record(
    index: int,
    employee: dict[str, Any],
    termination_date: date,
    rng: random.Random,
) -> dict[str, Any]:
    termination_type = rng.choices(
        ("voluntary", "involuntary"),
        weights=(72, 28),
        k=1,
    )[0]
    termination_timestamp = _timestamp(termination_date, hour=17)
    return {
        "termination_event_id": f"TERM{index:06d}",
        "employee_id": employee["employee_id"],
        "termination_date": termination_date.isoformat(),
        "termination_type": termination_type,
        "termination_reason": rng.choice(_TERMINATION_REASONS[termination_type]),
        "voluntary_flag": termination_type == "voluntary",
        "department_id": employee["department_id"],
        "created_at": termination_timestamp,
        "updated_at": termination_timestamp,
        "source_system": "hris",
    }


def generate_dataset(
    config: GenerationConfig | None = None,
    **overrides: Any,
) -> GeneratedDataset:
    """Generate repeatable departments, employees, hires, and terminations.

    Keyword overrides are accepted for convenient use in tests and scripts:
    ``generate_dataset(employees=20, seed=7)``.
    """
    if config is not None and overrides:
        raise TypeError("pass either config or keyword overrides, not both")
    config = config or GenerationConfig(**overrides)
    rng = random.Random(config.seed)
    departments = _generate_departments(config.as_of_date)
    employees: list[dict[str, Any]] = []
    hires: list[dict[str, Any]] = []
    terminations: list[dict[str, Any]] = []
    department_managers: dict[str, str] = {}

    for index in range(1, config.employees + 1):
        employee_id = f"EMP{index:06d}"
        department = departments[(index - 1) % len(departments)]
        department_id = str(department["department_id"])
        first_name = rng.choice(_FIRST_NAMES)
        last_name = rng.choice(_LAST_NAMES)
        hire_date = config.as_of_date - timedelta(
            days=_hire_offset(rng, config),
        )
        age_at_hire = rng.randint(21, 56)
        date_of_birth = hire_date - timedelta(
            days=age_at_hire * 365 + rng.randint(0, 364),
        )
        employment_type = rng.choices(
            ("full_time", "part_time", "contractor"),
            weights=(82, 10, 8),
            k=1,
        )[0]
        manager_employee_id = department_managers.get(department_id)
        if manager_employee_id is None:
            department_managers[department_id] = employee_id
        job_level_index = min(5, (index % 17) // 3)
        job_level = _JOB_LEVELS[job_level_index]
        job_id = f"JOB-{department_id[-3:]}-{job_level}"
        location_id = rng.choice(_LOCATIONS)

        termination_date: date | None = None
        if hire_date <= config.as_of_date - timedelta(
            days=31
        ) and rng.random() < _termination_probability(config):
            maximum_days = (config.as_of_date - hire_date).days
            termination_date = hire_date + timedelta(
                days=rng.randint(30, maximum_days),
            )
        status = "terminated" if termination_date else "active"
        created_at = _timestamp(hire_date)
        updated_at = _timestamp(termination_date or config.as_of_date, hour=17)
        safe_email_name = f"{_slug(first_name)}.{_slug(last_name)}.{index}"

        employee = {
            "employee_id": employee_id,
            "legal_entity_id": rng.choice(("LE-IN", "LE-UK", "LE-US")),
            "first_name": first_name,
            "last_name": last_name,
            "preferred_name": first_name if rng.random() < 0.72 else None,
            "date_of_birth": date_of_birth.isoformat(),
            "gender": rng.choices(_GENDERS, weights=(47, 47, 3, 3), k=1)[0],
            "email": f"{safe_email_name}@synthetic.peoplepulse.example",
            "phone": f"+91-555-{index:06d}",
            "hire_date": hire_date.isoformat(),
            "termination_date": (termination_date.isoformat() if termination_date else None),
            "employment_status": status,
            "employment_type": employment_type,
            "manager_employee_id": manager_employee_id,
            "department_id": department_id,
            "job_id": job_id,
            "job_level": job_level,
            "location_id": location_id,
            "cost_center_id": department["cost_center_id"],
            "worker_category": ("contingent" if employment_type == "contractor" else "employee"),
            "work_arrangement": rng.choice(_WORK_ARRANGEMENTS),
            "created_at": created_at,
            "updated_at": updated_at,
            "source_system": "hris",
        }
        hire = {
            "hire_event_id": f"HIRE{index:06d}",
            "employee_id": employee_id,
            "hire_date": hire_date.isoformat(),
            "hire_type": "external",
            "department_id": department_id,
            "job_id": job_id,
            "location_id": location_id,
            "requisition_id": f"REQ{index:06d}",
            "created_at": created_at,
            "updated_at": created_at,
            "source_system": "hris",
        }
        employees.append(employee)
        hires.append(hire)

        if termination_date is not None:
            terminations.append(_termination_record(index, employee, termination_date, rng))

    # Keep even small demo datasets useful for attrition analysis while retaining
    # the configured probabilistic distribution at normal portfolio scale.
    if config.employees >= 10 and not terminations:
        eligible = [
            (index, employee, date.fromisoformat(str(employee["hire_date"])))
            for index, employee in enumerate(employees, start=1)
            if date.fromisoformat(str(employee["hire_date"])) < config.as_of_date
        ]
        if eligible:
            index, employee, hire_date = min(eligible, key=lambda item: item[2])
            elapsed_days = (config.as_of_date - hire_date).days
            termination_date = hire_date + timedelta(days=max(1, elapsed_days // 2))
            employee["termination_date"] = termination_date.isoformat()
            employee["employment_status"] = "terminated"
            employee["updated_at"] = _timestamp(termination_date, hour=17)
            terminations.append(_termination_record(index, employee, termination_date, rng))

    dataset = GeneratedDataset(
        departments=departments,
        employees=employees,
        hires=hires,
        terminations=terminations,
    )
    apply_scenarios(
        dataset,
        scenarios=config.scenarios,
        rng=rng,
        as_of_date=config.as_of_date,
    )
    return dataset
