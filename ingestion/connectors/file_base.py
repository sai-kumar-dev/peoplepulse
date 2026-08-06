"""Shared incremental checkpoint behavior for file connectors."""

from __future__ import annotations

from ingestion.checkpoints import CheckpointStore, InMemoryCheckpointStore
from peoplepulse.common.models import Checkpoint


class FileConnectorBase:
    def __init__(
        self,
        *,
        source_name: str,
        entity_name: str,
        checkpoint_store: CheckpointStore | None,
    ) -> None:
        self.source_name = source_name
        self.entity_name = entity_name
        self.checkpoint_store = checkpoint_store or InMemoryCheckpointStore()
        self.proposed_checkpoint: Checkpoint | None = None

    def get_checkpoint(self) -> Checkpoint | None:
        return self.checkpoint_store.get(self.source_name, self.entity_name)

    def commit_checkpoint(self, checkpoint: Checkpoint) -> None:
        if checkpoint.source_name != self.source_name or checkpoint.entity_name != self.entity_name:
            raise ValueError("checkpoint source/entity does not match connector")
        self.checkpoint_store.commit(checkpoint)

    def _starting_offset(self, explicit_since: object | None) -> int:
        if explicit_since is not None:
            return max(0, int(str(explicit_since)))
        current = self.get_checkpoint()
        return max(0, int(str(current.value))) if current else 0
