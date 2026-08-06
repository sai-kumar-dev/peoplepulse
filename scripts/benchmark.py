"""Lightweight generator, ingestion, and API latency benchmark."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import tracemalloc
import urllib.request
from collections.abc import Sequence
from pathlib import Path


def _command(arguments: list[str]) -> dict[str, float | int | str]:
    started = time.perf_counter()
    completed = subprocess.run(arguments, check=True, capture_output=True, text=True)  # noqa: S603
    return {
        "command": " ".join(arguments[:3]),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "return_code": completed.returncode,
    }


def _api_latency(url: str, requests: int) -> dict[str, float | int]:
    durations: list[float] = []
    for _ in range(requests):
        started = time.perf_counter()
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310
            response.read()
        durations.append((time.perf_counter() - started) * 1000)
    durations.sort()
    return {
        "requests": requests,
        "p50_ms": round(durations[len(durations) // 2], 2),
        "p95_ms": round(durations[min(int(len(durations) * 0.95), len(durations) - 1)], 2),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--employees", type=int, default=10_000)
    parser.add_argument("--months", type=int, default=36)
    parser.add_argument("--output-dir", type=Path, default=Path("data/benchmark"))
    parser.add_argument("--api-url", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tracemalloc.start()
    generation = _command(
        [
            sys.executable,
            "-m",
            "data_generator.generate",
            "--employees",
            str(args.employees),
            "--months",
            str(args.months),
            "--seed",
            "42",
            "--output-dir",
            str(args.output_dir),
        ]
    )
    _, peak = tracemalloc.get_traced_memory()
    report: dict[str, object] = {
        "scale": {"employees": args.employees, "months": args.months},
        "generation": generation,
        "peak_python_memory_mb": round(peak / 1024 / 1024, 2),
        "row_counts": {
            path.stem: max(sum(1 for _ in path.open(encoding="utf-8")) - 1, 0)
            for path in args.output_dir.glob("*.csv")
        },
    }
    if args.api_url:
        report["api"] = _api_latency(args.api_url, 20)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
