"""flags schema (anomaly hypotheses)

Revision ID: 0008_flags
Revises: 0007_match_proposals
Create Date: 2026-07-10

Spec: specs/0017-anomaly-flags.md (Closes #40)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_flags"
down_revision: str | None = "0007_match_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "flags",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=False),
        sa.Column("subject_id", sa.Uuid(), nullable=False),
        sa.Column("rule", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column("reviewed_at", _TS, nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "rule IN ("
            "'single_bidder', 'short_window', 'threshold_hugging', 'repeat_winner', "
            "'shared_address', 'price_outlier', 'budget_payment_mismatch', 'overvote', 'smoke'"
            ")",
            name="ck_flags_rule",
        ),
        sa.CheckConstraint(
            "severity IN ('low', 'medium', 'high')",
            name="ck_flags_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'dismissed', 'confirmed')",
            name="ck_flags_status",
        ),
        sa.CheckConstraint(
            "evidence ? 'summary'",
            name="ck_flags_evidence_summary",
        ),
    )
    op.create_index("ix_flags_status", "flags", ["status"])
    op.create_index("ix_flags_rule", "flags", ["rule"])
    op.create_index("ix_flags_subject", "flags", ["subject_type", "subject_id"])
    op.execute(
        """
        CREATE UNIQUE INDEX uq_flags_open_rule_subject
        ON flags (rule, subject_type, subject_id)
        WHERE status = 'open'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_flags_open_rule_subject")
    op.drop_index("ix_flags_subject", table_name="flags")
    op.drop_index("ix_flags_rule", table_name="flags")
    op.drop_index("ix_flags_status", table_name="flags")
    op.drop_table("flags")
