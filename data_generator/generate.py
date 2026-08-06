"""Command line entry point for deterministic source-file generation."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from data_generator.generators import generate_dataset
from data_generator.models import GenerationConfig, GenerationResult
from data_generator.schemas import SCHEMAS
from peoplepulse.common.hashing import checksum_records


def _write_csv(
    path: Path,
    records: Sequence[Mapping[str, Any]],
    canonical_fields: Sequence[str],
) -> None:
    extra_fields = sorted(
        {key for record in records for key in record if key not in canonical_fields}
    )
    fieldnames = [*canonical_fields, *extra_fields]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)


def _write_json(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(records, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")


def write_dataset(
    output_dir: str | Path,
    *,
    config: GenerationConfig,
    formats: Iterable[str] = ("csv", "json"),
) -> GenerationResult:
    """Generate and atomically useful CSV/JSON source files plus a manifest."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    requested_formats = tuple(dict.fromkeys(value.lower() for value in formats))
    unsupported = sorted(set(requested_formats) - {"csv", "json"})
    if unsupported:
        raise ValueError(f"unsupported output format(s): {', '.join(unsupported)}")
    if not requested_formats:
        raise ValueError("at least one output format is required")

    dataset = generate_dataset(config)
    written: list[Path] = []
    checksums: dict[str, str] = {}
    counts: dict[str, int] = {}
    for entity_name, records in dataset.entities().items():
        counts[entity_name] = len(records)
        checksums[entity_name] = checksum_records(records)
        if "csv" in requested_formats:
            csv_path = destination / f"{entity_name}.csv"
            _write_csv(
                csv_path,
                records,
                SCHEMAS[entity_name].field_names,
            )
            written.append(csv_path)
        if "json" in requested_formats:
            json_path = destination / f"{entity_name}.json"
            _write_json(json_path, records)
            written.append(json_path)

    manifest = {
        "generator": "peoplepulse",
        "schema_versions": {entity: schema.version for entity, schema in SCHEMAS.items()},
        "config": {
            "employees": config.employees,
            "months": config.months,
            "scenario": config.scenario,
            "seed": config.seed,
            "as_of_date": config.as_of_date.isoformat(),
        },
        "counts": counts,
        "checksums": checksums,
        "formats": list(requested_formats),
    }
    manifest_path = destination / "manifest.json"
    with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    written.append(manifest_path)
    return GenerationResult(
        output_dir=destination,
        files=tuple(written),
        counts=counts,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic PeoplePulse HRIS data.",
    )
    parser.add_argument("--employees", type=int, default=100)
    parser.add_argument("--months", type=int, default=36)
    parser.add_argument(
        "--scenario",
        default="normal",
        help="Scenario name or a comma-separated list of scenarios.",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=date(2025, 1, 31))
    parser.add_argument("--output-dir", type=Path, default=Path("sample_data/generated"))
    parser.add_argument(
        "--format",
        "--formats",
        dest="formats",
        default="csv,json",
        help="csv, json, or a comma-separated combination (default: csv,json).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = GenerationConfig(
        employees=args.employees,
        months=args.months,
        scenario=args.scenario,
        seed=args.seed,
        as_of_date=args.as_of_date,
    )
    result = write_dataset(
        args.output_dir,
        config=config,
        formats=(item.strip() for item in args.formats.split(",") if item.strip()),
    )
    summary = ", ".join(f"{entity}={count}" for entity, count in result.counts.items())
    print(f"Generated {summary} in {result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
