"""Remove generated, reproducible local artifacts without touching source files."""

from __future__ import annotations

import shutil
from pathlib import Path

SAFE_TARGETS = (
    Path("artifacts"),
    Path("data/generated"),
    Path("data/checkpoints"),
    Path("data/dead_letter"),
    Path("dbt/target"),
    Path("dbt/logs"),
)


def main() -> None:
    root = Path.cwd().resolve()
    for relative in SAFE_TARGETS:
        target = (root / relative).resolve()
        if root not in target.parents:
            raise RuntimeError(f"Refusing to clean path outside project: {target}")
        if target.is_dir():
            shutil.rmtree(target)
            print(f"Removed reproducible directory: {relative}")
        elif target.exists():
            target.unlink()
            print(f"Removed reproducible file: {relative}")


if __name__ == "__main__":
    main()
