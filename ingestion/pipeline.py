"""End-to-end extraction/load coordination with safe checkpoint commits."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

from ingestion.connectors.base import SourceConnector
from ingestion.loaders.base import RawLoader
from ingestion.validation import RecordValidator
from peoplepulse.common.models import (
    BatchStatus,
    Checkpoint,
    ExtractionContext,
    LoadContext,
    LoadResult,
    SourceSchema,
    utc_now,
)


@dataclass(frozen=True, slots=True)
class PipelineRunResult:
    load_result: LoadResult
    checkpoint: Checkpoint | None
    checkpoint_committed: bool


def _checkpoint_text(checkpoint: Checkpoint | None) -> str | None:
    if checkpoint is None:
        return None
    value = checkpoint.value
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


class IngestionPipeline:
    """Materialize one extraction and commit progress only after a valid load."""

    def __init__(self, loader: RawLoader, *, pipeline_name: str = "people_data_ingestion"):
        self.loader = loader
        self.pipeline_name = pipeline_name

    def run(
        self,
        connector: SourceConnector,
        *,
        extraction_context: ExtractionContext,
        load_context: LoadContext | None = None,
        schema: SourceSchema | None = None,
        validator: RecordValidator | None = None,
    ) -> PipelineRunResult:
        records = list(connector.extract(extraction_context))
        proposed = getattr(connector, "proposed_checkpoint", None)
        context = load_context or LoadContext(
            batch_id=extraction_context.batch_id,
            pipeline_name=self.pipeline_name,
            source_name=extraction_context.source_name,
            entity_name=extraction_context.entity_name,
            started_at=utc_now(),
        )
        if proposed is not None:
            context = replace(
                context,
                checkpoint_value=_checkpoint_text(proposed),
            )
        load_result = self.loader.load(
            records,
            context=context,
            schema=schema or connector.get_schema(),
            validator=validator,
        )
        successful = load_result.metadata.status in {
            BatchStatus.COMPLETED,
            BatchStatus.COMPLETED_WITH_REJECTIONS,
        }
        reconciled = load_result.reconciliation is None or load_result.reconciliation.matched
        committed = False
        if successful and reconciled and proposed is not None:
            connector.commit_checkpoint(proposed)
            committed = True
        return PipelineRunResult(
            load_result=load_result,
            checkpoint=proposed,
            checkpoint_committed=committed,
        )
