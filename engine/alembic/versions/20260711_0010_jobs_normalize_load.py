"""Allow normalize_load job kind

Revision ID: 0010_jobs_normalize_load
Revises: 0009_review_decisions
Create Date: 2026-07-11

Spec: specs/0033-normalize-load-jobs.md (Closes #154)
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010_jobs_normalize_load"
down_revision: str | None = "0009_review_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_jobs_kind", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_kind",
        "jobs",
        "kind IN ('fetch_source', 'normalize_load')",
    )


def downgrade() -> None:
    op.execute("DELETE FROM jobs WHERE kind = 'normalize_load'")
    op.drop_constraint("ck_jobs_kind", "jobs", type_="check")
    op.create_check_constraint(
        "ck_jobs_kind",
        "jobs",
        "kind IN ('fetch_source')",
    )
