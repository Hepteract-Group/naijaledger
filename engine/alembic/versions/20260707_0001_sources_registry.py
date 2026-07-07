"""sources registry schema

Revision ID: 0001_sources
Revises:
Create Date: 2026-07-07

Spec: specs/0001-source-registry-schema.md (Closes #17)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_sources"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JURISDICTION = ("federal", "state", "lga")
SOURCE_CATEGORY = ("budget", "procurement", "payments", "company", "election", "other")
FETCH_METHOD = ("http", "scrapling", "playwright", "api", "manual")
SOURCE_FORMAT = ("pdf", "xlsx", "csv", "json", "html", "image")
HEALTH_STATUS = ("healthy", "degraded", "down", "tls_expired", "unknown")
SOURCE_STATUS = ("proposed", "approved", "retired")

ENUM_DEFS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("jurisdiction", JURISDICTION),
    ("source_category", SOURCE_CATEGORY),
    ("fetch_method", FETCH_METHOD),
    ("source_format", SOURCE_FORMAT),
    ("health_status", HEALTH_STATUS),
    ("source_status", SOURCE_STATUS),
)


def _enum(name: str, values: tuple[str, ...]) -> postgresql.ENUM:
    return postgresql.ENUM(*values, name=name, create_type=False)


def _create_enums() -> None:
    for name, values in ENUM_DEFS:
        postgresql.ENUM(*values, name=name).create(op.get_bind(), checkfirst=True)


def _drop_enums() -> None:
    for name, _values in reversed(ENUM_DEFS):
        postgresql.ENUM(name=name).drop(op.get_bind(), checkfirst=True)


def upgrade() -> None:
    _create_enums()

    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("jurisdiction", _enum("jurisdiction", JURISDICTION), nullable=False),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("category", _enum("source_category", SOURCE_CATEGORY), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("fetch_method", _enum("fetch_method", FETCH_METHOD), nullable=False),
        sa.Column("format", _enum("source_format", SOURCE_FORMAT), nullable=False),
        sa.Column("expected_cadence", sa.Interval(), nullable=True),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_hash", sa.Text(), nullable=True),
        sa.Column("schema_fingerprint", sa.Text(), nullable=True),
        sa.Column(
            "health_status",
            _enum("health_status", HEALTH_STATUS),
            server_default=sa.text("'unknown'::health_status"),
            nullable=False,
        ),
        sa.Column(
            "reliability_score",
            sa.Numeric(precision=4, scale=3),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum("source_status", SOURCE_STATUS),
            server_default=sa.text("'proposed'::source_status"),
            nullable=False,
        ),
        sa.Column("added_by", sa.Text(), nullable=True),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("url", "format", name="uq_sources_url_format"),
    )

    op.create_index("ix_sources_status", "sources", ["status"])
    op.create_index("ix_sources_category", "sources", ["category"])
    op.create_index("ix_sources_health_status", "sources", ["health_status"])


def downgrade() -> None:
    op.drop_index("ix_sources_health_status", table_name="sources")
    op.drop_index("ix_sources_category", table_name="sources")
    op.drop_index("ix_sources_status", table_name="sources")
    op.drop_table("sources")
    _drop_enums()
