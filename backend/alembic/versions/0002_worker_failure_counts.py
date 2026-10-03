"""Persist worker failure budgets without changing the task API.

Revision ID: 0002
Revises: 0001
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None

depends_on = None


def upgrade() -> None:
    # Expand-only: old code ignores these columns and its inserts retain defaults.
    op.add_column("tasks", sa.Column("stt_failures", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tasks", sa.Column("llm_failures", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("tasks", "llm_failures")
    op.drop_column("tasks", "stt_failures")
