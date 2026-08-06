"""PII-safe structured JSON logging."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

from api.app.core.context import current_request_id

_STANDARD_LOG_RECORD_FIELDS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)

_ALLOWED_CONTEXT_FIELDS = frozenset(
    {
        "duration_ms",
        "environment",
        "error_code",
        "http_method",
        "http_path",
        "record_count",
        "request_id",
        "run_id",
        "service",
        "status",
        "status_code",
    }
)


class JsonFormatter(logging.Formatter):
    """Render a conservative, allow-listed JSON log event."""

    def __init__(self, *, service: str, environment: str) -> None:
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "environment": self.environment,
            "event": record.getMessage(),
        }
        request_id = current_request_id()
        if request_id:
            payload["request_id"] = request_id
        for key, value in record.__dict__.items():
            if (
                key not in _STANDARD_LOG_RECORD_FIELDS
                and key in _ALLOWED_CONTEXT_FIELDS
                and value is not None
            ):
                payload[key] = value
        if record.exc_info:
            # Exception text can contain source payloads or connection strings. Emit only
            # the exception class; detailed traces remain a local debug concern.
            exception_type = record.exc_info[0]
            if exception_type is not None:
                payload["exception_type"] = exception_type.__name__
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(*, service: str, environment: str, level: str) -> None:
    """Configure the root logger exactly once for this process."""

    root = logging.getLogger()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter(service=service, environment=environment))
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
