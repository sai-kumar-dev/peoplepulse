"""Prometheus metrics with deliberately low-cardinality, non-PII labels."""

from prometheus_client import Counter, Histogram

PIPELINE_RUNS = Counter(
    "pipeline_runs_total",
    "Number of pipeline runs.",
    ("pipeline", "status"),
)
PIPELINE_FAILURES = Counter(
    "pipeline_failures_total",
    "Number of failed pipeline runs.",
    ("pipeline", "error_code"),
)
PIPELINE_DURATION = Histogram(
    "pipeline_duration_seconds",
    "Pipeline runtime in seconds.",
    ("pipeline",),
)
RECORDS_EXTRACTED = Counter(
    "records_extracted_total",
    "Records extracted from a source.",
    ("source", "entity"),
)
RECORDS_LOADED = Counter(
    "records_loaded_total",
    "Records loaded into the raw layer.",
    ("source", "entity"),
)
RECORDS_REJECTED = Counter(
    "records_rejected_total",
    "Records rejected by validation.",
    ("source", "entity", "error_code"),
)
QUALITY_FAILURES = Counter(
    "data_quality_failures_total",
    "Failed quality checks.",
    ("check_name", "severity"),
)
API_REQUESTS = Counter(
    "api_requests_total",
    "API requests.",
    ("method", "route", "status"),
)
API_DURATION = Histogram(
    "api_request_duration_seconds",
    "API request duration.",
    ("method", "route"),
)
