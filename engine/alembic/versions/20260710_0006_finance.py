"""canonical public-finance schema

Revision ID: 0006_finance
Revises: 0005_jobs
Create Date: 2026-07-10

Spec: specs/0011-canonical-finance-schema.md (Closes #32)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_finance"
down_revision: str | None = "0005_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)


def _timestamps() -> tuple[sa.Column[object], sa.Column[object]]:
    return (
        sa.Column("created_at", _TS, server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.text("now()"), nullable=False),
    )


def upgrade() -> None:
    created_at, updated_at = _timestamps()
    op.create_table(
        "parties",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("party_type", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column(
            "aliases",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column(
            "identifiers",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("address", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("merged_into_id", sa.Uuid(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["merged_into_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "party_type IN ('company', 'person', 'agency')",
            name="ck_parties_party_type",
        ),
    )
    op.create_index("ix_parties_canonical_name", "parties", ["canonical_name"])
    op.create_index(
        "ix_parties_merged_into",
        "parties",
        ["merged_into_id"],
        postgresql_where=sa.text("merged_into_id IS NOT NULL"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_parties_type_name ON parties (party_type, lower(canonical_name))"
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "party_relationships",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("from_party_id", sa.Uuid(), nullable=False),
        sa.Column("to_party_id", sa.Uuid(), nullable=False),
        sa.Column("relationship", sa.Text(), nullable=False),
        sa.Column("weight", sa.Numeric(4, 3), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["from_party_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["to_party_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "from_party_id",
            "to_party_id",
            "relationship",
            name="uq_party_relationships_edge",
        ),
        sa.CheckConstraint("from_party_id <> to_party_id", name="ck_party_relationships_not_self"),
        sa.CheckConstraint(
            "relationship IN ("
            "'owns', 'director_of', 'significant_control', 'same_address', 'associated'"
            ")",
            name="ck_party_relationships_relationship",
        ),
        sa.CheckConstraint(
            "weight IS NULL OR (weight >= 0 AND weight <= 1)",
            name="ck_party_relationships_weight",
        ),
    )

    created_at, updated_at = _timestamps()
    op.create_table(
        "tenders",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("ocid", sa.Text(), nullable=True),
        sa.Column("agency_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=True),
        sa.Column("value_amount", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.Text(), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("bidding_opens_at", _TS, nullable=True),
        sa.Column("bidding_closes_at", _TS, nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agency_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "method IS NULL OR method IN ('open', 'selective', 'limited', 'direct')",
            name="ck_tenders_method",
        ),
    )
    op.execute("CREATE UNIQUE INDEX uq_tenders_ocid ON tenders (ocid) WHERE ocid IS NOT NULL")
    op.create_index("ix_tenders_agency_id", "tenders", ["agency_id"])

    created_at, updated_at = _timestamps()
    op.create_table(
        "awards",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tender_id", sa.Uuid(), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("value_amount", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.Text(), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("awarded_at", _TS, nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["tender_id"], ["tenders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["parties.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_awards_tender_id", "awards", ["tender_id"])
    op.create_index("ix_awards_supplier_id", "awards", ["supplier_id"])

    created_at, updated_at = _timestamps()
    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("award_id", sa.Uuid(), nullable=True),
        sa.Column("supplier_id", sa.Uuid(), nullable=False),
        sa.Column("agency_id", sa.Uuid(), nullable=False),
        sa.Column("value_amount", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.Text(), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("signed_at", _TS, nullable=True),
        sa.Column("period", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["award_id"], ["awards.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["supplier_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agency_id"], ["parties.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_contracts_award_id", "contracts", ["award_id"])
    op.create_index("ix_contracts_supplier_id", "contracts", ["supplier_id"])
    op.create_index("ix_contracts_agency_id", "contracts", ["agency_id"])

    created_at, updated_at = _timestamps()
    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=True),
        sa.Column("agency_id", sa.Uuid(), nullable=False),
        sa.Column("beneficiary_id", sa.Uuid(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.Text(), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("paid_at", _TS, nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("source_ref", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["contract_id"], ["contracts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agency_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["beneficiary_id"], ["parties.id"], ondelete="RESTRICT"),
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_payments_source_ref ON payments (source_ref) "
        "WHERE source_ref IS NOT NULL"
    )
    op.create_index("ix_payments_agency_id", "payments", ["agency_id"])
    op.create_index("ix_payments_contract_id", "payments", ["contract_id"])

    created_at, updated_at = _timestamps()
    op.create_table(
        "budget_lines",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("agency_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("allocated_amount", sa.BigInteger(), nullable=True),
        sa.Column("revised_amount", sa.BigInteger(), nullable=True),
        sa.Column("released_amount", sa.BigInteger(), nullable=True),
        sa.Column("utilised_amount", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.Text(), server_default=sa.text("'NGN'"), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        created_at,
        updated_at,
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["agency_id"], ["parties.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint(
            "fiscal_year",
            "agency_id",
            "code",
            "jurisdiction",
            name="uq_budget_lines_natural",
        ),
        sa.CheckConstraint(
            "jurisdiction IN ('federal', 'state', 'lga')",
            name="ck_budget_lines_jurisdiction",
        ),
    )


def downgrade() -> None:
    op.drop_table("budget_lines")
    op.drop_index("ix_payments_contract_id", table_name="payments")
    op.drop_index("ix_payments_agency_id", table_name="payments")
    op.execute("DROP INDEX IF EXISTS uq_payments_source_ref")
    op.drop_table("payments")
    op.drop_index("ix_contracts_agency_id", table_name="contracts")
    op.drop_index("ix_contracts_supplier_id", table_name="contracts")
    op.drop_index("ix_contracts_award_id", table_name="contracts")
    op.drop_table("contracts")
    op.drop_index("ix_awards_supplier_id", table_name="awards")
    op.drop_index("ix_awards_tender_id", table_name="awards")
    op.drop_table("awards")
    op.drop_index("ix_tenders_agency_id", table_name="tenders")
    op.execute("DROP INDEX IF EXISTS uq_tenders_ocid")
    op.drop_table("tenders")
    op.drop_table("party_relationships")
    op.execute("DROP INDEX IF EXISTS uq_parties_type_name")
    op.drop_index("ix_parties_merged_into", table_name="parties")
    op.drop_index("ix_parties_canonical_name", table_name="parties")
    op.drop_table("parties")
