"""Paginated REST connector implemented with the standard library."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from ingestion.checkpoints import CheckpointStore, InMemoryCheckpointStore
from ingestion.validation import infer_schema
from peoplepulse.common.errors import ErrorCode, PeoplePulseError
from peoplepulse.common.models import (
    Checkpoint,
    ExtractionContext,
    Record,
    SourceSchema,
    utc_now,
)

Requester = Callable[[str, Mapping[str, str], float], Any]


class RESTConnector:
    def __init__(
        self,
        base_url: str,
        endpoint: str,
        *,
        entity_name: str,
        source_name: str = "rest",
        schema: SourceSchema | None = None,
        checkpoint_field: str | None = None,
        checkpoint_parameter: str = "updated_after",
        checkpoint_store: CheckpointStore | None = None,
        headers: Mapping[str, str] | None = None,
        records_key: str = "records",
        next_key: str = "next",
        page_size: int = 1000,
        timeout_seconds: float = 30.0,
        retries: int = 3,
        requester: Requester | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        if not base_url.lower().startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        self.base_url = base_url.rstrip("/")
        self.endpoint = "/" + endpoint.lstrip("/")
        self.entity_name = entity_name
        self.source_name = source_name
        self._schema = schema
        self.checkpoint_field = checkpoint_field
        self.checkpoint_parameter = checkpoint_parameter
        self.checkpoint_store = checkpoint_store or InMemoryCheckpointStore()
        self.headers = dict(headers or {})
        self.records_key = records_key
        self.next_key = next_key
        self.page_size = page_size
        self.timeout_seconds = timeout_seconds
        self.retries = retries
        self.requester = requester or self._stdlib_request
        self.sleeper = sleeper
        self.proposed_checkpoint: Checkpoint | None = None

    @staticmethod
    def _stdlib_request(
        url: str,
        headers: Mapping[str, str],
        timeout: float,
    ) -> Any:
        request = urllib.request.Request(url, headers=dict(headers))  # noqa: S310
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return json.loads(response.read().decode("utf-8"))

    def _request(self, url: str) -> Any:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise PeoplePulseError(
                ErrorCode.SOURCE_UNAVAILABLE,
                "REST pagination returned an unsupported URL scheme.",
                context={"source": self.source_name, "entity": self.entity_name},
            )
        for attempt in range(self.retries + 1):
            try:
                return self.requester(url, self.headers, self.timeout_seconds)
            except (
                OSError,
                TimeoutError,
                urllib.error.URLError,
                json.JSONDecodeError,
            ) as exc:
                if attempt >= self.retries:
                    raise PeoplePulseError(
                        ErrorCode.SOURCE_UNAVAILABLE,
                        "REST source request failed.",
                        retryable=True,
                        context={
                            "source": self.source_name,
                            "entity": self.entity_name,
                            "attempts": attempt + 1,
                        },
                        cause=exc,
                    ) from exc
                self.sleeper(min(2**attempt, 30))
        raise AssertionError("unreachable")

    def get_checkpoint(self) -> Checkpoint | None:
        return self.checkpoint_store.get(self.source_name, self.entity_name)

    def commit_checkpoint(self, checkpoint: Checkpoint) -> None:
        if checkpoint.source_name != self.source_name or checkpoint.entity_name != self.entity_name:
            raise ValueError("checkpoint source/entity does not match connector")
        self.checkpoint_store.commit(checkpoint)

    def _initial_url(self, context: ExtractionContext) -> str:
        query: dict[str, Any] = {"limit": min(self.page_size, context.limit or self.page_size)}
        since = context.since
        if since is None:
            checkpoint = self.get_checkpoint()
            since = checkpoint.value if checkpoint else None
        if since is not None:
            query[self.checkpoint_parameter] = since
        query.update(context.parameters)
        return f"{self.base_url}{self.endpoint}?{urllib.parse.urlencode(query, doseq=True)}"

    def _page_records(self, payload: Any) -> tuple[list[dict[str, Any]], str | None]:
        next_url: str | None = None
        if isinstance(payload, list):
            value = payload
        elif isinstance(payload, dict):
            value = payload.get(self.records_key, [])
            next_value = payload.get(self.next_key)
            if next_value:
                next_url = urllib.parse.urljoin(
                    f"{self.base_url}{self.endpoint}",
                    str(next_value),
                )
        else:
            value = None
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise PeoplePulseError(
                ErrorCode.SOURCE_SCHEMA_INVALID,
                "REST response must contain a list of record objects.",
                context={"source": self.source_name, "entity": self.entity_name},
            )
        return [dict(item) for item in value], next_url

    def get_schema(self) -> SourceSchema:
        if self._schema is not None:
            return self._schema
        context = ExtractionContext(
            batch_id="schema-inspection",
            source_name=self.source_name,
            entity_name=self.entity_name,
            limit=1,
        )
        records, _ = self._page_records(self._request(self._initial_url(context)))
        return infer_schema(self.entity_name, records)

    def extract(self, context: ExtractionContext) -> Iterable[Record]:
        next_url: str | None = self._initial_url(context)
        emitted = 0
        last_checkpoint: Any = context.since
        while next_url:
            records, next_page = self._page_records(self._request(next_url))
            for record in records:
                if context.limit is not None and emitted >= context.limit:
                    next_url = None
                    break
                yield record
                emitted += 1
                if self.checkpoint_field is not None:
                    value = record.get(self.checkpoint_field)
                    if value is not None:
                        last_checkpoint = value
            else:
                next_url = next_page
                continue
            break
        if self.checkpoint_field is not None and last_checkpoint is not None:
            self.proposed_checkpoint = Checkpoint(
                source_name=self.source_name,
                entity_name=self.entity_name,
                value=last_checkpoint,
                updated_at=utc_now(),
            )
