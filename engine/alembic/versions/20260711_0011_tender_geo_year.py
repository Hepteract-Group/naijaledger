"""Add state_code, lga, fiscal_year to tenders

Revision ID: 0011_tender_geo_year
Revises: 0010_jobs_normalize_load
Create Date: 2026-07-11

Spec: specs/0034-geo-year-facets.md (Closes #151)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_tender_geo_year"
down_revision: str | None = "0010_jobs_normalize_load"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tenders", sa.Column("state_code", sa.Text(), nullable=True))
    op.add_column("tenders", sa.Column("lga", sa.Text(), nullable=True))
    op.add_column("tenders", sa.Column("fiscal_year", sa.Integer(), nullable=True))
    op.create_index("ix_tenders_state_code", "tenders", ["state_code"])
    op.create_index("ix_tenders_fiscal_year", "tenders", ["fiscal_year"])
    op.execute(
        "CREATE INDEX ix_tenders_lga_lower ON tenders (lower(lga)) WHERE lga IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tenders_lga_lower")
    op.drop_index("ix_tenders_fiscal_year", table_name="tenders")
    op.drop_index("ix_tenders_state_code", table_name="tenders")
    op.drop_column("tenders", "fiscal_year")
    op.drop_column("tenders", "lga")
    op.drop_column("tenders", "state_code")
