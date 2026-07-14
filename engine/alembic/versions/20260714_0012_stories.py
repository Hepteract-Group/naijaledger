"""Published narrative stories (scrollytelling)

Revision ID: 0012_stories
Revises: 0011_tender_geo_year
Create Date: 2026-07-14

Spec: specs/0038-stories-read-api.md (Closes #137)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_stories"
down_revision: str | None = "0011_tender_geo_year"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "stories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("lede", sa.Text(), nullable=False),
        sa.Column("steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("next_label", sa.Text(), nullable=False),
        sa.Column("next_to", sa.Text(), nullable=False),
        sa.Column("review_decision_id", sa.Uuid(), nullable=True),
        sa.Column("published_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_decision_id"],
            ["review_decisions.id"],
            name="fk_stories_review_decision_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_stories_slug"),
    )
    op.create_index("ix_stories_published_at", "stories", ["published_at"])


def downgrade() -> None:
    op.drop_index("ix_stories_published_at", table_name="stories")
    op.drop_table("stories")
