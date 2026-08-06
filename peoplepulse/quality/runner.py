"""Quality result persistence and critical-failure policy."""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from peoplepulse.errors import ErrorCode, PeoplePulseError
from peoplepulse.quality.checks import CheckResult, CheckStatus


class QualityGateError(PeoplePulseError):
    """Raised only after all results have been persisted."""


@dataclass(slots=True)
class QualityRunner:
    output_path: Path
    run_id: str = field(default_factory=lambda: str(uuid4()))

    def evaluate(
        self, results: Iterable[CheckResult], *, fail_on_critical: bool = True
    ) -> list[CheckResult]:
        materialized = list(results)
        self.persist(materialized)
        failures = [result for result in materialized if result.status is CheckStatus.FAIL]
        if failures and fail_on_critical:
            names = ", ".join(sorted({result.check_name for result in failures}))
            raise QualityGateError(
                code=ErrorCode.DATA_QUALITY_FAILED,
                summary="Critical data-quality checks failed",
                detail=f"Failed aggregate checks: {names}. Inspect the quality artifact.",
                retryable=False,
                run_id=self.run_id,
            )
        return materialized

    def persist(self, results: Iterable[CheckResult]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": self.run_id,
            "results": [result.as_dict() for result in results],
        }
        self.output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
