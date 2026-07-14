"""Add sources.ingest_role (leaf/catalog/discovery/search)

Revision ID: 0013_source_ingest_role
Revises: 0012_stories
Create Date: 2026-07-14

Spec: specs/0039-federal-discovery-rescope.md (Closes #82)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_source_ingest_role"
down_revision: str | None = "0012_stories"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "ingest_role",
            sa.Text(),
            server_default=sa.text("'leaf'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_sources_ingest_role",
        "sources",
        "ingest_role IN ('leaf', 'catalog', 'discovery_ui', 'search_ui')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_sources_ingest_role", "sources", type_="check")
    op.drop_column("sources", "ingest_role")
