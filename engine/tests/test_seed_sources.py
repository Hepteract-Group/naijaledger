from sqlalchemy import text

from naijaledger.seeds.catalog import SEED_CATALOG
from naijaledger.seeds.run import apply_seed_catalog


def test_seed_catalog_is_idempotent(db_connection) -> None:
    first = apply_seed_catalog(db_connection)
    second = apply_seed_catalog(db_connection)

    assert first["created"] == len(SEED_CATALOG)
    assert first["approved"] == len(SEED_CATALOG)
    assert second["created"] == 0
    assert second["skipped"] == len(SEED_CATALOG)
    assert second["approved"] == 0


def test_seed_catalog_entries_are_approved(db_connection) -> None:
    apply_seed_catalog(db_connection)

    rows = db_connection.execute(text("SELECT status FROM sources")).all()
    assert len(rows) == len(SEED_CATALOG)
    assert all(row.status == "approved" for row in rows)
