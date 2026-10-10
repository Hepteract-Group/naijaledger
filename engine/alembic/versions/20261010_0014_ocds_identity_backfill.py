"""Backfill OCDS identity keys and add unique indexes

Revision ID: 0014_ocds_identity_backfill
Revises: 0013_source_ingest_role
Create Date: 2026-10-10

Backfills meta->>'ocds_award_id' and meta->>'ocds_contract_id' for existing rows,
merges multi-supplier award duplicates into additional_supplier_refs, and adds
unique partial indexes to prevent future duplicates.

Related: #203 OCP state bulk awards, commit 3312fe3 identity semantics
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0014_ocds_identity_backfill"
down_revision: str | None = "0013_source_ingest_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: Backfill ocds_award_id in meta for awards that don't have it
    # Generate synthetic IDs based on row data to maintain stability across re-runs
    conn.execute(
        text(
            """
            UPDATE awards
            SET meta = jsonb_set(
                COALESCE(meta, '{}'::jsonb),
                '{ocds_award_id}',
                to_jsonb(CONCAT('backfill:award:', id::text))
            )
            WHERE meta->>'ocds_award_id' IS NULL
            """
        )
    )

    # Step 2: Backfill ocds_contract_id in meta for contracts that don't have it
    # Use the same synthetic ID pattern
    conn.execute(
        text(
            """
            UPDATE contracts
            SET meta = jsonb_set(
                COALESCE(meta, '{}'::jsonb),
                '{ocds_contract_id}',
                to_jsonb(CONCAT('backfill:contract:', id::text))
            )
            WHERE meta->>'ocds_contract_id' IS NULL
            """
        )
    )

    # Step 3: Handle multi-supplier award duplicates
    # Find awards with same (tender_id, ocds_award_id) but different suppliers
    # Keep the oldest row, merge other suppliers into additional_supplier_refs
    conn.execute(
        text(
            """
            WITH duplicates AS (
                SELECT
                    tender_id,
                    meta->>'ocds_award_id' AS ocds_award_id,
                    array_agg(id ORDER BY created_at) AS award_ids,
                    array_agg(supplier_id ORDER BY created_at) AS supplier_ids
                FROM awards
                WHERE meta->>'ocds_award_id' IS NOT NULL
                GROUP BY tender_id, meta->>'ocds_award_id'
                HAVING count(*) > 1
            ),
            keeper_updates AS (
                SELECT
                    award_ids[1] AS keeper_id,
                    jsonb_build_array(supplier_ids[2:array_length(supplier_ids, 1)]) AS extra_suppliers
                FROM duplicates
            )
            UPDATE awards a
            SET meta = jsonb_set(
                COALESCE(a.meta, '{}'::jsonb),
                '{additional_supplier_refs}',
                ku.extra_suppliers
            )
            FROM keeper_updates ku
            WHERE a.id = ku.keeper_id
            """
        )
    )

    # Step 4: Delete duplicate award rows (keep only the first)
    conn.execute(
        text(
            """
            DELETE FROM awards
            WHERE id IN (
                SELECT unnest(award_ids[2:array_length(award_ids, 1)])
                FROM (
                    SELECT
                        array_agg(id ORDER BY created_at) AS award_ids
                    FROM awards
                    WHERE meta->>'ocds_award_id' IS NOT NULL
                    GROUP BY tender_id, meta->>'ocds_award_id'
                    HAVING count(*) > 1
                ) subq
            )
            """
        )
    )

    # Step 5: Add unique partial indexes to prevent future duplicates
    # Awards: unique (tender_id, meta->>'ocds_award_id') where ocds_award_id is not null
    op.create_index(
        "ix_awards_tender_ocds_id",
        "awards",
        ["tender_id", sa.text("((meta->>'ocds_award_id'))")],
        unique=True,
        postgresql_where=sa.text("meta->>'ocds_award_id' IS NOT NULL"),
    )

    # Contracts: unique (agency_id, meta->>'ocds_contract_id') where ocds_contract_id is not null
    op.create_index(
        "ix_contracts_agency_ocds_id",
        "contracts",
        ["agency_id", sa.text("((meta->>'ocds_contract_id'))")],
        unique=True,
        postgresql_where=sa.text("meta->>'ocds_contract_id' IS NOT NULL"),
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index(
        "ix_contracts_agency_ocds_id",
        table_name="contracts",
        postgresql_where=sa.text("meta->>'ocds_contract_id' IS NOT NULL"),
    )
    op.drop_index(
        "ix_awards_tender_ocds_id",
        table_name="awards",
        postgresql_where=sa.text("meta->>'ocds_award_id' IS NOT NULL"),
    )

    # Note: We do not undo the data backfills or unmerge duplicates in downgrade
    # as that would be destructive. The backfilled IDs remain but indexes are removed.
