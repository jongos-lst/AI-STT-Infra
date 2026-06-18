from __future__ import annotations

import pytest

from app.core.errors import InvalidStateTransition
from app.domain.task import TERMINAL, TaskStatus, transition


@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (TaskStatus.PENDING_UPLOAD, TaskStatus.QUEUED),
        (TaskStatus.QUEUED, TaskStatus.STT_RUNNING),
        (TaskStatus.STT_RUNNING, TaskStatus.STT_DONE),
        (TaskStatus.STT_DONE, TaskStatus.LLM_RUNNING),
        (TaskStatus.LLM_RUNNING, TaskStatus.DONE),
        # Workers may re-enter running states on redelivery.
        (TaskStatus.STT_RUNNING, TaskStatus.STT_RUNNING),
        (TaskStatus.LLM_RUNNING, TaskStatus.LLM_RUNNING),
        # FAILED is reachable from any non-terminal stage.
        (TaskStatus.QUEUED, TaskStatus.FAILED),
        (TaskStatus.STT_RUNNING, TaskStatus.FAILED),
        (TaskStatus.LLM_RUNNING, TaskStatus.FAILED),
    ],
)
def test_valid_transitions(src: TaskStatus, dst: TaskStatus) -> None:
    assert transition(src, dst) == dst


@pytest.mark.parametrize(
    ("src", "dst"),
    [
        (TaskStatus.PENDING_UPLOAD, TaskStatus.STT_RUNNING),  # skip QUEUED
        (TaskStatus.STT_DONE, TaskStatus.DONE),               # skip LLM
        (TaskStatus.QUEUED, TaskStatus.LLM_RUNNING),          # skip STT
        (TaskStatus.DONE, TaskStatus.LLM_RUNNING),            # leave terminal
        (TaskStatus.FAILED, TaskStatus.STT_RUNNING),
    ],
)
def test_invalid_transitions(src: TaskStatus, dst: TaskStatus) -> None:
    with pytest.raises(InvalidStateTransition):
        transition(src, dst)


def test_terminal_states_exact() -> None:
    assert frozenset({TaskStatus.DONE, TaskStatus.FAILED}) == TERMINAL
