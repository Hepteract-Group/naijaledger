"""review_decisions schema (human publication gate)

Revision ID: 0009_review_decisions
Revises: 0008_flags
Create Date: 2026-07-10

Spec: specs/0022-review-decisions.md (Closes #45)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_review_decisions"
down_revision: str | None = "0008_flags"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "review_decisions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reviewer", sa.Text(), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("decided_at", _TS, nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "decision IN ('pending', 'approve_publish', 'reject', 'needs_more_evidence')",
            name="ck_review_decisions_decision",
        ),
        sa.CheckConstraint(
            "("
            "decision = 'pending' AND reviewer IS NULL AND decided_at IS NULL"
            ") OR ("
            "decision <> 'pending' AND reviewer IS NOT NULL AND decided_at IS NOT NULL"
            ")",
            name="ck_review_decisions_pending_fields",
        ),
    )
    op.create_index("ix_review_decisions_subject", "review_decisions", ["subject_type", "subject_id"])
    op.create_index("ix_review_decisions_decision", "review_decisions", ["decision"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_review_decisions_pending_subject
        ON review_decisions (subject_type, subject_id)
        WHERE decision = 'pending'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_review_decisions_pending_subject")
    op.drop_index("ix_review_decisions_decision", table_name="review_decisions")
    op.drop_index("ix_review_decisions_subject", table_name="review_decisions")
    op.drop_table("review_decisions")
