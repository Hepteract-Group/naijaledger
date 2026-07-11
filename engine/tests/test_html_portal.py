from pathlib import Path

from sqlalchemy import text

from naijaledger.finance.html_portal import (
    ekiti_html_to_ocds_package,
    parse_naira_amount,
    parse_portal_date,
)
from naijaledger.finance.ocds import normalize_ocds_document
from naijaledger.finance.portal_load_cli import load_ekiti_html
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import create_source

_FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_naira_and_dates() -> None:
    assert parse_naira_amount("₦947,554.05") == 947554.05
    assert parse_naira_amount("N25,000,000.00") == 25_000_000.0
    assert parse_portal_date("Monday, July 6, 2026") == "2026-07-06"
    assert parse_portal_date("") is None


def test_ekiti_html_to_ocds_package_fixture() -> None:
    html = (_FIXTURES / "ekiti_procurements.html").read_bytes()
    package = ekiti_html_to_ocds_package(html, max_rows=10)
    assert package["meta"]["release_count"] == 2
    ocids = {release["ocid"] for release in package["releases"]}
    assert "ocds-6olpk7-BSP/BPP/CONO/72026/77421663" in ocids
    releases = normalize_ocds_document(package)
    assert len(releases) == 2
    assert all(release.tender is not None for release in releases)
    assert all(release.awards for release in releases)


def test_load_ekiti_html_persists_parties_and_tenders(db_connection) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Ekiti fixture source",
            jurisdiction="state",
            region="Ekiti",
            category="procurement",
            url="https://ocdsportal.azurewebsites.net/Home/Procurements",
            fetch_method="scrapling",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    fetch_id = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, 'ekiti-html-hash', 'sha256/ekiti-html-hash'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "url": source.url},
    ).scalar_one()
    document_id = db_connection.execute(
        text(
            """
            INSERT INTO documents (
                source_id, first_fetch_id, sha256, format, archive_key, title
            ) VALUES (
                :source_id, :fetch_id, 'ekiti-html-hash', 'html',
                'sha256/ekiti-html-hash', 'Ekiti fixture'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "fetch_id": fetch_id},
    ).scalar_one()

    html = (_FIXTURES / "ekiti_procurements.html").read_bytes()
    summary = load_ekiti_html(db_connection, html, document_id=document_id, max_rows=10)
    assert summary["release_count"] == 2
    assert summary["tenders_upserted"] == 2
    assert summary["parties_upserted"] >= 2

    tender_count = db_connection.execute(text("SELECT count(*) FROM tenders")).scalar_one()
    party_count = db_connection.execute(text("SELECT count(*) FROM parties")).scalar_one()
    assert tender_count >= 2
    assert party_count >= 2

    # Idempotent re-load
    second = load_ekiti_html(db_connection, html, document_id=document_id, max_rows=10)
    assert second["release_count"] == 2
    assert db_connection.execute(text("SELECT count(*) FROM tenders")).scalar_one() == tender_count
