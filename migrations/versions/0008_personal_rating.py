"""Personal rating (spec 020): each reading entry may carry a rating from 1 to 5.

Revision ID: 0008_personal_rating
Revises: 0007_optional_story_series
Create Date: 2026-11-27

Existing entries get no rating. The downgrade drops the column and the ratings with it; the
backup taken before every deploy keeps them (spec 020 Clarifications, AC-13).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_personal_rating"
down_revision: str | None = "0007_optional_story_series"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reading_entry", sa.Column("rating", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "reading_entry_rating_check", "reading_entry", "rating BETWEEN 1 AND 5"
    )


def downgrade() -> None:
    op.drop_constraint("reading_entry_rating_check", "reading_entry", type_="check")
    op.drop_column("reading_entry", "rating")
