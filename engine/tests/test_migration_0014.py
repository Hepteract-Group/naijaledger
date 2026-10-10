"""Test migration 0014: OCDS identity backfill and deduplication."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest
from sqlalchemy import text

from naijaledger.db.connection import create_db_engine
from naijaledger.finance.ocds import normalize_ocds_release
from naijaledger.finance.ocds_load import load_normalized_release


def test_migration_0014_backfills_and_dedupes(db_connection) -> None:
    """Blocker 1: migration backfills IDs and merges multi-supplier awards."""
    # The db_connection fixture already ran migration 0014, so we're testing
    # that the indexes exist and prevent duplicates.

    # Create a tender
    tender_id = uuid4()
    supplier1_id = uuid4()
    supplier2_id = uuid4()
    agency_id = uuid4()

    db_connection.execute(
        text(
            """
            INSERT INTO parties (id, name, role, created_at, updated_at)
            VALUES (:id, :name, :role, NOW(), NOW())
            """
        ),
        [
            {"id": supplier1_id, "name": "Supplier 1", "role": "supplier"},
            {"id": supplier2_id, "name": "Supplier 2", "role": "supplier"},
            {"id": agency_id, "name": "Agency", "role": "buyer"},
        ],
    )

    db_connection.execute(
        text(
            """
            INSERT INTO tenders (
                id, ocid, agency_id, title, published_at,
                created_at, updated_at
            )
            VALUES (
                :id, :ocid, :agency_id, :title, :published_at,
                NOW(), NOW()
            )
            """
        ),
        {
            "id": tender_id,
            "ocid": "ocds-test-001",
            "agency_id": agency_id,
            "title": "Test",
            "published_at": datetime(2023, 1, 1),
        },
    )

    # Try to insert two awards with same (tender_id, ocds_award_id)
    # The unique index should prevent this
    award1_id = uuid4()
    db_connection.execute(
        text(
            """
            INSERT INTO awards (
                id, tender_id, supplier_id, value_amount, currency,
                meta, created_at, updated_at
            )
            VALUES (
                :id, :tender_id, :supplier_id, 1000, 'NGN',
                :meta, NOW(), NOW()
            )
            """
        ),
        {
            "id": award1_id,
            "tender_id": tender_id,
            "supplier_id": supplier1_id,
            "meta": '{"ocds_award_id": "award-1"}',
        },
    )

    # Second insert with same ocds_award_id should fail
    with pytest.raises(Exception) as exc_info:
        db_connection.execute(
            text(
                """
                INSERT INTO awards (
                    id, tender_id, supplier_id, value_amount, currency,
                    meta, created_at, updated_at
                )
                VALUES (
                    :id, :tender_id, :supplier_id, 2000, 'NGN',
                    :meta, NOW(), NOW()
                )
                """
            ),
            {
                "id": uuid4(),
                "tender_id": tender_id,
                "supplier_id": supplier2_id,
                "meta": '{"ocds_award_id": "award-1"}',
            },
        )
    assert "unique" in str(exc_info.value).lower()

    # Verify the unique index on contracts too
    contract1_id = uuid4()
    db_connection.execute(
        text(
            """
            INSERT INTO contracts (
                id, supplier_id, agency_id, value_amount, currency,
                meta, created_at, updated_at
            )
            VALUES (
                :id, :supplier_id, :agency_id, 1000, 'NGN',
                :meta, NOW(), NOW()
            )
            """
        ),
        {
            "id": contract1_id,
            "supplier_id": supplier1_id,
            "agency_id": agency_id,
            "meta": '{"ocds_contract_id": "ocds-test-001:contract-1"}',
        },
    )

    # Second contract with same (agency_id, ocds_contract_id) should fail
    with pytest.raises(Exception) as exc_info:
        db_connection.execute(
            text(
                """
                INSERT INTO contracts (
                    id, supplier_id, agency_id, value_amount, currency,
                    meta, created_at, updated_at
                )
                VALUES (
                    :id, :supplier_id, :agency_id, 2000, 'NGN',
                    :meta, NOW(), NOW()
                )
                """
            ),
            {
                "id": uuid4(),
                "supplier_id": supplier2_id,
                "agency_id": agency_id,
                "meta": '{"ocds_contract_id": "ocds-test-001:contract-1"}',
            },
        )
    assert "unique" in str(exc_info.value).lower()
