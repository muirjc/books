"""Stories without a series (spec 019): a story's series and number become optional, both
or neither, and each book remembers the order its stories were added.

Revision ID: 0007_optional_story_series
Revises: 0006_summary_drafts
Create Date: 2026-11-26

The downgrade is refused while any story has no series, rather than inventing one
(spec 019 AC-14).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_optional_story_series"
down_revision: str | None = "0006_summary_drafts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BOTH_OR_NEITHER = "(series_id IS NULL) = (series_number IS NULL)"


def upgrade() -> None:
    op.alter_column("story", "series_id", nullable=True)
    op.alter_column("story", "series_number", nullable=True)
    op.create_check_constraint("story_series_both_or_neither", "story", BOTH_OR_NEITHER)
    op.add_column("book_story", sa.Column("position", sa.Integer(), nullable=True))
    # Today's order (series name, then number) becomes each book's positions (research R1).
    op.execute(
        """
        UPDATE book_story bs SET position = ordered.n
        FROM (
          SELECT bs2.book_id, bs2.story_id,
                 row_number() OVER (
                   PARTITION BY bs2.book_id
                   ORDER BY lower(se.name), st.series_number, st.id
                 ) AS n
          FROM book_story bs2
          JOIN story st ON st.id = bs2.story_id
          LEFT JOIN series se ON se.id = st.series_id
        ) ordered
        WHERE bs.book_id = ordered.book_id AND bs.story_id = ordered.story_id
        """
    )
    # Later links take the next value of a sequence, so a book's new stories come after its
    # earlier ones and two concurrent adds never share a position (research R2).
    op.execute("CREATE SEQUENCE book_story_position_seq OWNED BY book_story.position START WITH 1")
    op.execute(
        "SELECT setval('book_story_position_seq', "
        "(SELECT coalesce(max(position), 0) + 1 FROM book_story), false)"
    )
    op.alter_column(
        "book_story",
        "position",
        nullable=False,
        server_default=sa.text("nextval('book_story_position_seq')"),
    )
    op.create_check_constraint("book_story_position_check", "book_story", "position >= 1")


def downgrade() -> None:
    missing = op.get_bind().scalar(sa.text("SELECT count(*) FROM story WHERE series_id IS NULL"))
    if missing:
        raise RuntimeError(
            f"{missing} stories have no series: give each one a series and number, or delete "
            "them, before downgrading (spec 019 AC-14)"
        )
    op.drop_constraint("book_story_position_check", "book_story", type_="check")
    op.drop_column("book_story", "position")  # drops the sequence it owns
    op.drop_constraint("story_series_both_or_neither", "story", type_="check")
    op.alter_column("story", "series_number", nullable=False)
    op.alter_column("story", "series_id", nullable=False)
