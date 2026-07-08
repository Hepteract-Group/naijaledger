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


def test_seed_retires_unreliable_open_treasury(db_connection) -> None:
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

    assert updated.status == "retired"
    assert summary["retired"] >= 1


def test_seed_corrects_nocopo_to_open_data(db_connection) -> None:
    legacy = create_source(
        db_connection,
        SourceCreate(
            name="Nigeria Open Contracting Portal (NOCOPO)",
            jurisdiction="federal",
            category="procurement",
            url="https://nocopo.bpp.gov.ng/",
            fetch_method="http",
            format="html",
        ),
    )
    approve_source(db_connection, legacy.id, approved_by="test")

    summary = apply_seed_catalog(db_connection)
    updated = get_source(db_connection, legacy.id)

    assert updated.url == "https://nocopo.bpp.gov.ng/Open-Data"
    assert summary["corrected"] >= 1


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


def test_seed_corrects_state_portal_data_paths(db_connection) -> None:
    legacy = create_source(
        db_connection,
        SourceCreate(
            name="Ekiti State Open Contracting Portal",
            jurisdiction="state",
            region="Ekiti",
            category="procurement",
            url="https://ocdsportal.azurewebsites.net/",
            fetch_method="scrapling",
            format="html",
        ),
    )
    approve_source(db_connection, legacy.id, approved_by="test")

    summary = apply_seed_catalog(db_connection)
    updated = get_source(db_connection, legacy.id)

    assert updated.url == "https://ocdsportal.azurewebsites.net/Home/Procurements"
    assert summary["corrected"] >= 1


def test_seed_substitutes_empty_kwara_with_gombe(db_connection) -> None:
    legacy = create_source(
        db_connection,
        SourceCreate(
            name="Kwara State Open Contracting Portal",
            jurisdiction="state",
            region="Kwara",
            category="procurement",
            url="https://kwppa.kwarastate.gov.ng/ocds-portal/awarded-contracts",
            fetch_method="scrapling",
            format="html",
        ),
    )
    approve_source(db_connection, legacy.id, approved_by="test")

    summary = apply_seed_catalog(db_connection)
    updated = get_source(db_connection, legacy.id)

    assert updated.url == "https://project.dueprocess.gm.gov.ng/projects"
    assert updated.region == "Gombe"
    assert summary["corrected"] >= 1


def test_seed_corrects_anambra_tenders_to_awards(db_connection) -> None:
    legacy = create_source(
        db_connection,
        SourceCreate(
            name="Anambra State Public Procurement Portal",
            jurisdiction="state",
            region="Anambra",
            category="procurement",
            url="https://eprocure.bpp.an.gov.ng/tenders.php",
            fetch_method="scrapling",
            format="html",
        ),
    )
    approve_source(db_connection, legacy.id, approved_by="test")

    summary = apply_seed_catalog(db_connection)
    updated = get_source(db_connection, legacy.id)

    assert updated.url == "https://eprocure.bpp.an.gov.ng/awarded_contracts.php"
    assert summary["corrected"] >= 1


def test_seed_corrects_budget_and_neiti_to_document_indexes(db_connection) -> None:
    budget = create_source(
        db_connection,
        SourceCreate(
            name="Budget Office of the Federation",
            jurisdiction="federal",
            category="budget",
            url="https://budgetoffice.gov.ng/",
            fetch_method="http",
            format="html",
        ),
    )
    neiti = create_source(
        db_connection,
        SourceCreate(
            name="NEITI",
            jurisdiction="federal",
            category="other",
            url="https://neiti.gov.ng/",
            fetch_method="http",
            format="html",
        ),
    )
    approve_source(db_connection, budget.id, approved_by="test")
    approve_source(db_connection, neiti.id, approved_by="test")

    summary = apply_seed_catalog(db_connection)

    assert get_source(db_connection, budget.id).url.endswith("/budget-documents")
    assert get_source(db_connection, neiti.id).url == "https://neiti.gov.ng/documents/all"
    assert summary["corrected"] >= 2
