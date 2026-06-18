"""Task entity + state machine.

The state machine is the source of truth: every transition listed here is allowed,
everything else raises. Workers and the API both go through `transition()`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from app.core.errors import InvalidStateTransition


class TaskStatus(StrEnum):
    PENDING_UPLOAD = "PENDING_UPLOAD"   # row exists, signed URL issued
    QUEUED = "QUEUED"                   # upload complete, event in outbox
    STT_RUNNING = "STT_RUNNING"
    STT_DONE = "STT_DONE"
    LLM_RUNNING = "LLM_RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


# adjacency list — keep tiny and explicit; new stage = new edges + entries here.
_ALLOWED: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING_UPLOAD: frozenset({TaskStatus.QUEUED, TaskStatus.FAILED}),
    TaskStatus.QUEUED:         frozenset({TaskStatus.STT_RUNNING, TaskStatus.FAILED}),
    TaskStatus.STT_RUNNING:    frozenset({TaskStatus.STT_DONE, TaskStatus.STT_RUNNING, TaskStatus.FAILED}),
    TaskStatus.STT_DONE:       frozenset({TaskStatus.LLM_RUNNING, TaskStatus.FAILED}),
    TaskStatus.LLM_RUNNING:    frozenset({TaskStatus.DONE, TaskStatus.LLM_RUNNING, TaskStatus.FAILED}),
    TaskStatus.DONE:           frozenset(),
    TaskStatus.FAILED:         frozenset(),
}

TERMINAL: frozenset[TaskStatus] = frozenset({TaskStatus.DONE, TaskStatus.FAILED})


def transition(current: TaskStatus, target: TaskStatus) -> TaskStatus:
    """Return target if the move is legal; raise otherwise."""
    if current == target:
        # Re-running RUNNING states is allowed (worker retry), but moving anywhere else
        # from a terminal state is not.
        if current in TERMINAL:
            raise InvalidStateTransition(f"{current} is terminal")
        return target
    if target not in _ALLOWED[current]:
        raise InvalidStateTransition(f"{current} → {target} not allowed")
    return target


@dataclass(slots=True)
class Task:
    id: UUID
    tenant_id: str
    status: TaskStatus
    audio_uri: str | None = None
    audio_sha256: str | None = None
    audio_bytes: int | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def new(cls, tenant_id: str, audio_sha256: str, audio_bytes: int, filename: str) -> Task:
        return cls(
            id=uuid4(),
            tenant_id=tenant_id,
            status=TaskStatus.PENDING_UPLOAD,
            audio_sha256=audio_sha256,
            audio_bytes=audio_bytes,
            metadata={"filename": filename},
        )

    def move_to(self, target: TaskStatus, *, error: str | None = None) -> None:
        prev = self.status
        self.status = transition(self.status, target)
        self.updated_at = datetime.now(UTC)
        if error is not None:
            self.error = error
        # Late import so the metrics module is optional (e.g. for cold scripts).
        try:
            from app.core.metrics import record_transition
            record_transition(prev.value, self.status.value)
        except Exception:
            pass
