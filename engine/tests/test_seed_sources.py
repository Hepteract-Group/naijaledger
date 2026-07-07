from sqlalchemy import text

from naijaledger.seeds.catalog import SEED_CATALOG
from naijaledger.seeds.run import apply_seed_catalog
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source, get_source


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


def test_seed_corrects_obsolete_open_treasury_url(db_connection) -> None:
    legacy = create_source(
        db_connection,
        SourceCreate(
            name="Open Treasury Portal",
            jurisdiction="federal",
            category="payments",
            url="https://payment.gov.ng/",
            fetch_method="http",
            format="html",
        ),
    )
    approve_source(db_connection, legacy.id, approved_by="test")

    summary = apply_seed_catalog(db_connection)
    updated = get_source(db_connection, legacy.id)

    assert updated.url == "https://opentreasury.gov.ng/"
    assert summary["corrected"] == 1


def test_seed_retires_substituted_state_portals(db_connection) -> None:
    legacy = create_source(
        db_connection,
        SourceCreate(
            name="Ondo State Open Contracting Portal",
            jurisdiction="state",
            region="Ondo",
            category="procurement",
            url="https://ondobppaocds.azurewebsites.net/",
            fetch_method="scrapling",
            format="html",
        ),
    )
    approve_source(db_connection, legacy.id, approved_by="test")

    summary = apply_seed_catalog(db_connection)
    updated = get_source(db_connection, legacy.id)

    assert updated.status == "retired"
    assert summary["retired"] >= 1
