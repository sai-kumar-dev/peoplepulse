"""Durable and in-memory incremental checkpoint implementations."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from peoplepulse.common.errors import ErrorCode, PeoplePulseError
from peoplepulse.common.models import Checkpoint


class CheckpointStore(Protocol):
    def get(self, source_name: str, entity_name: str) -> Checkpoint | None: ...

    def commit(self, checkpoint: Checkpoint) -> None: ...


class InMemoryCheckpointStore:
    """Thread-safe checkpoint store suitable for tests and one-shot processes."""

    def __init__(self) -> None:
        self._values: dict[tuple[str, str], Checkpoint] = {}
        self._lock = threading.Lock()

    def get(self, source_name: str, entity_name: str) -> Checkpoint | None:
        with self._lock:
            return self._values.get((source_name, entity_name))

    def commit(self, checkpoint: Checkpoint) -> None:
        with self._lock:
            self._values[(checkpoint.source_name, checkpoint.entity_name)] = checkpoint


class FileCheckpointStore:
    """Small JSON checkpoint store using atomic file replacement."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def _read(self) -> dict[str, dict[str, Any]]:
        if not self.path.exists():
            return {}
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise PeoplePulseError(
                ErrorCode.CHECKPOINT_FAILED,
                "Checkpoint file could not be read.",
                context={"path": str(self.path)},
                cause=exc,
            ) from exc
        if not isinstance(raw, dict):
            raise PeoplePulseError(
                ErrorCode.CHECKPOINT_FAILED,
                "Checkpoint file has an invalid top-level value.",
                context={"path": str(self.path)},
            )
        return raw

    @staticmethod
    def _key(source_name: str, entity_name: str) -> str:
        return f"{source_name}::{entity_name}"

    def get(self, source_name: str, entity_name: str) -> Checkpoint | None:
        with self._lock:
            item = self._read().get(self._key(source_name, entity_name))
        if not item:
            return None
        return Checkpoint(
            source_name=source_name,
            entity_name=entity_name,
            value=item["value"],
            updated_at=datetime.fromisoformat(item["updated_at"]),
        )

    def commit(self, checkpoint: Checkpoint) -> None:
        with self._lock:
            values = self._read()
            values[self._key(checkpoint.source_name, checkpoint.entity_name)] = {
                "value": checkpoint.value,
                "updated_at": checkpoint.updated_at.isoformat(),
            }
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            try:
                temporary.write_text(
                    json.dumps(values, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, self.path)
            except OSError as exc:
                raise PeoplePulseError(
                    ErrorCode.CHECKPOINT_FAILED,
                    "Checkpoint file could not be committed.",
                    context={"path": str(self.path)},
                    cause=exc,
                ) from exc


class SQLiteCheckpointStore:
    """Transactional checkpoints shared by local pipeline processes."""

    def __init__(
        self,
        database: str | Path = ":memory:",
        *,
        connection: sqlite3.Connection | None = None,
    ) -> None:
        self._owns_connection = connection is None
        self.connection = connection or sqlite3.connect(str(database))
        self.connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_checkpoints (
                source_name TEXT NOT NULL,
                entity_name TEXT NOT NULL,
                checkpoint_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (source_name, entity_name)
            )
            """
        )
        self.connection.commit()

    def get(self, source_name: str, entity_name: str) -> Checkpoint | None:
        row = self.connection.execute(
            """
            SELECT checkpoint_json, updated_at
            FROM ingestion_checkpoints
            WHERE source_name = ? AND entity_name = ?
            """,
            (source_name, entity_name),
        ).fetchone()
        if row is None:
            return None
        return Checkpoint(
            source_name=source_name,
            entity_name=entity_name,
            value=json.loads(row[0]),
            updated_at=datetime.fromisoformat(row[1]),
        )

    def commit(self, checkpoint: Checkpoint) -> None:
        try:
            with self.connection:
                self.connection.execute(
                    """
                    INSERT INTO ingestion_checkpoints (
                        source_name, entity_name, checkpoint_json, updated_at
                    ) VALUES (?, ?, ?, ?)
                    ON CONFLICT (source_name, entity_name) DO UPDATE SET
                        checkpoint_json = excluded.checkpoint_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        checkpoint.source_name,
                        checkpoint.entity_name,
                        json.dumps(checkpoint.value, sort_keys=True),
                        checkpoint.updated_at.isoformat(),
                    ),
                )
        except sqlite3.Error as exc:
            raise PeoplePulseError(
                ErrorCode.CHECKPOINT_FAILED,
                "SQLite checkpoint could not be committed.",
                cause=exc,
            ) from exc

    def close(self) -> None:
        if self._owns_connection:
            self.connection.close()
