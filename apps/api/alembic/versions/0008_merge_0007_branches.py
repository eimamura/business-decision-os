"""Merge 0007_session_title and 0007_session_events branches.

Revision ID: 0008_merge_0007_branches
Revises: 0007_session_title, 0007_session_events
Create Date: 2026-05-22
"""

from __future__ import annotations

from alembic import op

revision = "0008_merge_0007_branches"
down_revision = ("0007_session_title", "0007_session_events")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
