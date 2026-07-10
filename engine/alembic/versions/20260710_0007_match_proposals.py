"""party_match_proposals (E6.2)

Revision ID: 0007_match_proposals
Revises: 0006_finance
Create Date: 2026-07-10

Spec: specs/0015-llm-match-adjudication.md (Closes #37)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_match_proposals"
down_revision: str | None = "0006_finance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def upgrade() -> None:
    op.create_table(
        "party_match_proposals",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("left_party_id", sa.Uuid(), nullable=False),
        sa.Column("right_party_id", sa.Uuid(), nullable=False),
        sa.Column("match_score", sa.Numeric(4, 3), nullable=False),
        sa.Column("match_rule", sa.Text(), nullable=False),
        sa.Column("match_reason", sa.Text(), nullable=False),
        sa.Column("opinion", sa.Text(), nullable=False),
        sa.Column("opinion_rationale", sa.Text(), nullable=False),
        sa.Column("adjudicator", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("suggested_survivor_id", sa.Uuid(), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("resolved_at", _TS, nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["left_party_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["right_party_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["suggested_survivor_id"], ["parties.id"], ondelete="SET NULL"),
        sa.CheckConstraint("left_party_id <> right_party_id", name="ck_party_match_proposals_not_self"),
        sa.CheckConstraint(
            "match_rule IN ('deterministic', 'probabilistic')",
            name="ck_party_match_proposals_match_rule",
        ),
        sa.CheckConstraint(
            "opinion IN ('same_entity', 'different', 'uncertain')",
            name="ck_party_match_proposals_opinion",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'confirmed', 'rejected', 'withdrawn')",
            name="ck_party_match_proposals_status",
        ),
        sa.CheckConstraint(
            "match_score >= 0 AND match_score <= 1",
            name="ck_party_match_proposals_score",
        ),
    )
    op.create_index(
        "ix_party_match_proposals_status",
        "party_match_proposals",
        ["status"],
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_party_match_proposals_pending_pair
        ON party_match_proposals (
            LEAST(left_party_id, right_party_id),
            GREATEST(left_party_id, right_party_id)
        )
        WHERE status = 'pending'
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_party_match_proposals_pending_pair")
    op.drop_index("ix_party_match_proposals_status", table_name="party_match_proposals")
    op.drop_table("party_match_proposals")
