"""extractions + provenance_edges schema

Revision ID: 0004_extractions
Revises: 0003_documents
Create Date: 2026-07-10

Spec: specs/0009-extraction-contract.md (Closes #88)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_extractions"
down_revision: str | None = "0003_documents"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "extractions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("method_version", sa.Text(), nullable=False),
        sa.Column("derivation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=True),
        sa.Column("content_type_conf", sa.Numeric(4, 3), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
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
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "derivation IN ('extracted', 'inferred', 'ambiguous')",
            name="ck_extractions_derivation",
        ),
        sa.CheckConstraint(
            "status IN ('parsed', 'quarantined', 'unsupported', 'failed')",
            name="ck_extractions_status",
        ),
        sa.CheckConstraint(
            "method IN ("
            "'xlsx', 'csv', 'json', 'pdf_text', 'pdf_table', 'ocr', 'vision_llm'"
            ")",
            name="ck_extractions_method",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_extractions_confidence_range",
        ),
        sa.CheckConstraint(
            "(derivation = 'extracted' AND confidence = 1)"
            " OR (derivation IN ('inferred', 'ambiguous') AND confidence < 1)",
            name="ck_extractions_derivation_confidence",
        ),
    )
    op.create_index("ix_extractions_document_id", "extractions", ["document_id"])
    op.create_index("ix_extractions_status", "extractions", ["status"])
    op.create_index("ix_extractions_derivation", "extractions", ["derivation"])

    op.create_table(
        "provenance_edges",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("subject_type", sa.Text(), nullable=True),
        sa.Column("subject_id", sa.Uuid(), nullable=True),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("extraction_id", sa.Uuid(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("region", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("derivation", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=False),
        sa.Column("verified_by", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["extraction_id"], ["extractions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "derivation IN ('extracted', 'inferred', 'ambiguous')",
            name="ck_provenance_edges_derivation",
        ),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name="ck_provenance_edges_confidence_range",
        ),
        sa.CheckConstraint(
            "(derivation = 'extracted' AND confidence = 1)"
            " OR (derivation IN ('inferred', 'ambiguous') AND confidence < 1)",
            name="ck_provenance_edges_derivation_confidence",
        ),
    )
    op.create_index("ix_provenance_edges_document_id", "provenance_edges", ["document_id"])
    op.create_index(
        "ix_provenance_edges_extraction_id",
        "provenance_edges",
        ["extraction_id"],
    )
    op.create_index(
        "ix_provenance_edges_subject",
        "provenance_edges",
        ["subject_type", "subject_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_provenance_edges_subject", table_name="provenance_edges")
    op.drop_index("ix_provenance_edges_extraction_id", table_name="provenance_edges")
    op.drop_index("ix_provenance_edges_document_id", table_name="provenance_edges")
    op.drop_table("provenance_edges")
    op.drop_index("ix_extractions_derivation", table_name="extractions")
    op.drop_index("ix_extractions_status", table_name="extractions")
    op.drop_index("ix_extractions_document_id", table_name="extractions")
    op.drop_table("extractions")
