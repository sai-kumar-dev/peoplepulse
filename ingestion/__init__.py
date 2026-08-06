"""Connector-based, idempotent ingestion framework."""

from ingestion.pipeline import IngestionPipeline, PipelineRunResult

__all__ = ["IngestionPipeline", "PipelineRunResult"]
