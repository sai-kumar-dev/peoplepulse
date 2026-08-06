"""Configuration and result models for synthetic data generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class GenerationConfig:
    employees: int = 100
    months: int = 36
    scenario: str = "normal"
    seed: int = 42
    as_of_date: date = date(2025, 1, 31)

    def __post_init__(self) -> None:
        if self.employees < 1:
            raise ValueError("employees must be at least 1")
        if self.months < 1:
            raise ValueError("months must be at least 1")
        if self.months > 600:
            raise ValueError("months cannot exceed 600")

    @property
    def scenarios(self) -> tuple[str, ...]:
        values = tuple(item.strip().lower() for item in self.scenario.split(",") if item.strip())
        return values or ("normal",)


@dataclass(slots=True)
class GeneratedDataset:
    departments: list[dict[str, Any]] = field(default_factory=list)
    employees: list[dict[str, Any]] = field(default_factory=list)
    hires: list[dict[str, Any]] = field(default_factory=list)
    terminations: list[dict[str, Any]] = field(default_factory=list)

    def entities(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "departments": self.departments,
            "employees": self.employees,
            "hires": self.hires,
            "terminations": self.terminations,
        }


@dataclass(frozen=True, slots=True)
class GenerationResult:
    output_dir: Path
    files: tuple[Path, ...]
    counts: dict[str, int]
