from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from naijaledger.archive.types import ArchiveStoreResult
from naijaledger.config import Settings
from naijaledger.documents.service import get_document_by_sha256
from naijaledger.fetch.link_discovery import (
    discover_and_fetch_catalog_children,
    extract_artifact_links,
    extract_subdir_catalog_links,
    has_successful_fetch_for_url,
    is_budget_year_catalog_url,
    is_catalog_source,
)
from naijaledger.fetch.service import create_fetch_record
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_catalog_fixture(name: str) -> bytes:
    return (_FIXTURES_DIR / name).read_bytes()


def test_is_catalog_source_recognizes_lagos_and_jigawa() -> None:
    assert is_catalog_source("https://www.lagosppa.gov.ng/registered-awards/")
    assert is_catalog_source("https://dueprocess.jigawastate.gov.ng/contracts")
    assert is_catalog_source(
        "https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents"
    )
    assert not is_catalog_source("https://example.com/awards")


def test_extract_subdir_catalog_links_budget_office_index() -> None:
    html = _load_catalog_fixture("budget_office_index.html")
    base = "https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents"
    years = extract_subdir_catalog_links(html, base_url=base)
    assert years[0].endswith("/2026-budget")
    assert any(link.endswith("/2025-budget") for link in years)
    assert any(link.endswith("/2017-approved-budget") for link in years)
    assert any(link.endswith("/2024-appropriation-amendment-act") for link in years)
    assert all(is_budget_year_catalog_url(link) for link in years)
    assert all("evil.example" not in link for link in years)


def test_extract_artifact_links_budget_office_year_page() -> None:
    html = _load_catalog_fixture("budget_office_2025.html")
    links = extract_artifact_links(
        html,
        base_url=(
            "https://budgetoffice.gov.ng/index.php/resources/"
            "internal-resources/budget-documents/2025-budget"
        ),
    )
    assert any(link.endswith("/download") for link in links)
    assert any("/viewdocument/" in link for link in links)
    assert all(link.startswith("https://budgetoffice.gov.ng/") for link in links)


def test_extract_artifact_links_lagos_fixture() -> None:
    html = _load_catalog_fixture("lagos_registered_awards.html")
    links = extract_artifact_links(
        html,
        base_url="https://www.lagosppa.gov.ng/registered-awards/",
    )
    assert any("AWARD-REGISTER-NOVEMBER-2025.pdf" in link for link in links)
    assert all(link.startswith("https://www.lagosppa.gov.ng/") for link in links)


def test_extract_artifact_links_jigawa_fixture() -> None:
    html = _load_catalog_fixture("jigawa_contracts.html")
    links = extract_artifact_links(
        html,
        base_url="https://dueprocess.jigawastate.gov.ng/contracts",
    )
    assert any("/storage/contracts/reports/" in link and link.endswith(".pdf") for link in links)


def test_extract_artifact_links_ignores_off_origin() -> None:
    html = b"""
    <html><body>
      <a href="/local/report.pdf">local</a>
      <a href="https://evil.example/steal.pdf">remote</a>
    </body></html>
    """
    links = extract_artifact_links(html, base_url="https://www.lagosppa.gov.ng/registered-awards/")
    assert links == ["https://www.lagosppa.gov.ng/local/report.pdf"]


def test_discover_and_fetch_catalog_children_archives_pdf(
    db_connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Lagos State Public Procurement Agency — Registered Awards",
            jurisdiction="state",
            region="Lagos",
            category="procurement",
            url="https://www.lagosppa.gov.ng/registered-awards/",
            fetch_method="scrapling",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")
    catalog_html = _load_catalog_fixture("lagos_registered_awards.html")
    pdf_bytes = b"%PDF-1.4 lagos award register"

    catalog_fetch = create_fetch_record(
        db_connection,
        source_id=approved.id,
        url=approved.url,
        requested_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
        status_code=200,
        ok=True,
        byte_count=len(catalog_html),
        sha256="cataloghash",
        headers={"content-type": "text/html"},
        error=None,
        archive_key="sha256/cataloghash",
    )

    from naijaledger.documents.service import upsert_document_from_fetch

    catalog_doc = upsert_document_from_fetch(
        db_connection,
        source_id=approved.id,
        first_fetch_id=catalog_fetch.id,
        sha256="cataloghash",
        archive_key="sha256/cataloghash",
        format="html",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url).endswith(".pdf"):
            return httpx.Response(
                200,
                content=pdf_bytes,
                headers={"content-type": "application/pdf"},
            )
        raise AssertionError(f"unexpected URL {request.url}")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    minio_client = MagicMock()

    def fake_store(
        _client: object,
        _bucket: str,
        data: bytes,
        **kwargs: object,
    ) -> ArchiveStoreResult:
        return ArchiveStoreResult(
            archive_key="sha256/childpdf",
            content_hash="childpdf",
            byte_count=len(data),
            created=True,
        )

    monkeypatch.setattr("naijaledger.fetch.capture.store_raw_bytes", fake_store)

    catalog_result = {
        "fetch_record_id": catalog_fetch.id,
        "ok": True,
        "archive_key": "sha256/cataloghash",
        "content_hash": "cataloghash",
        "document_id": catalog_doc["document_id"],
    }
    summary = discover_and_fetch_catalog_children(
        db_connection,
        approved,
        catalog_result=catalog_result,
        catalog_html=catalog_html,
        catalog_url=approved.url,
        http_client=http_client,
        minio_client=minio_client,
        bucket="test-bucket",
        requested_at=datetime(2026, 7, 8, 12, 1, tzinfo=UTC),
    )

    assert summary["attempted"] >= 1
    assert summary["succeeded"] >= 1
    child_document = get_document_by_sha256(db_connection, "childpdf")
    assert child_document is not None
    assert child_document.format == "pdf"
    assert child_document.meta is not None
    assert child_document.meta["discovery"]["parent_document_id"] == str(catalog_doc["document_id"])


def test_discover_skips_child_url_already_fetched(
    db_connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Jigawa State Open Contracting Portal",
            jurisdiction="state",
            region="Jigawa",
            category="procurement",
            url="https://dueprocess.jigawastate.gov.ng/contracts",
            fetch_method="scrapling",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")
    child_url = "https://dueprocess.jigawastate.gov.ng/storage/contracts/reports/existing.pdf"
    catalog_html = f'<html><a href="{child_url}">report</a></html>'.encode()

    create_fetch_record(
        db_connection,
        source_id=approved.id,
        url=child_url,
        requested_at=datetime(2026, 7, 8, 11, 0, tzinfo=UTC),
        status_code=200,
        ok=True,
        byte_count=100,
        sha256="existingchild",
        headers={"content-type": "application/pdf"},
        error=None,
        archive_key="sha256/existingchild",
    )
    assert has_successful_fetch_for_url(db_connection, source_id=approved.id, url=child_url)

    catalog_fetch = create_fetch_record(
        db_connection,
        source_id=approved.id,
        url=approved.url,
        requested_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
        status_code=200,
        ok=True,
        byte_count=len(catalog_html),
        sha256="jigcatalog",
        headers={"content-type": "text/html"},
        error=None,
        archive_key="sha256/jigcatalog",
    )
    from naijaledger.documents.service import upsert_document_from_fetch

    catalog_doc = upsert_document_from_fetch(
        db_connection,
        source_id=approved.id,
        first_fetch_id=catalog_fetch.id,
        sha256="jigcatalog",
        archive_key="sha256/jigcatalog",
        format="html",
    )

    http_called = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        http_called["count"] += 1
        return httpx.Response(200, content=b"pdf")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "naijaledger.fetch.capture.store_raw_bytes",
        lambda *_args, **_kwargs: ArchiveStoreResult(
            archive_key="sha256/x",
            content_hash="x",
            byte_count=1,
            created=True,
        ),
    )

    summary = discover_and_fetch_catalog_children(
        db_connection,
        approved,
        catalog_result={
            "fetch_record_id": catalog_fetch.id,
            "ok": True,
            "archive_key": "sha256/jigcatalog",
            "content_hash": "jigcatalog",
            "document_id": catalog_doc["document_id"],
        },
        catalog_html=catalog_html,
        catalog_url=approved.url,
        http_client=http_client,
        minio_client=MagicMock(),
        bucket="test-bucket",
        requested_at=datetime(2026, 7, 8, 12, 1, tzinfo=UTC),
    )

    assert http_called["count"] == 0
    assert summary["attempted"] == 0


def test_discover_budget_office_expands_year_pages(
    db_connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index_url = (
        "https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents"
    )
    source = create_source(
        db_connection,
        SourceCreate(
            name="Budget Office of the Federation — Budget Documents",
            jurisdiction="federal",
            region=None,
            category="budget",
            url=index_url,
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")
    catalog_html = _load_catalog_fixture("budget_office_index.html")
    year_html = _load_catalog_fixture("budget_office_2025.html")
    pdf_bytes = b"%PDF-1.4 appropriation act"

    catalog_fetch = create_fetch_record(
        db_connection,
        source_id=approved.id,
        url=approved.url,
        requested_at=datetime(2026, 7, 11, 12, 0, tzinfo=UTC),
        status_code=200,
        ok=True,
        byte_count=len(catalog_html),
        sha256="budgetindex",
        headers={"content-type": "text/html"},
        error=None,
        archive_key="sha256/budgetindex",
    )
    from naijaledger.documents.service import upsert_document_from_fetch

    catalog_doc = upsert_document_from_fetch(
        db_connection,
        source_id=approved.id,
        first_fetch_id=catalog_fetch.id,
        sha256="budgetindex",
        archive_key="sha256/budgetindex",
        format="html",
    )

    fetched_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        fetched_urls.append(url)
        if url.rstrip("/").endswith("-budget") or "appropriation-amendment" in url:
            return httpx.Response(
                200,
                content=year_html,
                headers={"content-type": "text/html"},
            )
        if url.rstrip("/").endswith("/download"):
            return httpx.Response(
                200,
                content=pdf_bytes,
                headers={"content-type": "application/pdf"},
            )
        raise AssertionError(f"unexpected URL {url}")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(
        "naijaledger.fetch.capture.store_raw_bytes",
        lambda _client, _bucket, data, **_kwargs: ArchiveStoreResult(
            archive_key="sha256/budgetpdf",
            content_hash="budgetpdf",
            byte_count=len(data),
            created=True,
        ),
    )

    summary = discover_and_fetch_catalog_children(
        db_connection,
        approved,
        catalog_result={
            "fetch_record_id": catalog_fetch.id,
            "ok": True,
            "archive_key": "sha256/budgetindex",
            "content_hash": "budgetindex",
            "document_id": catalog_doc["document_id"],
        },
        catalog_html=catalog_html,
        catalog_url=index_url,
        http_client=http_client,
        minio_client=MagicMock(),
        bucket="test-bucket",
        requested_at=datetime(2026, 7, 11, 12, 1, tzinfo=UTC),
        settings=Settings(catalog_subdir_max=1, catalog_discovery_max_children=5),
    )

    assert any("/2026-budget" in url for url in fetched_urls)
    assert any(url.rstrip("/").endswith("/download") for url in fetched_urls)
    assert not any("/viewdocument/" in url for url in fetched_urls)
    assert summary["attempted"] >= 1
    assert summary["succeeded"] >= 1
    child_document = get_document_by_sha256(db_connection, "budgetpdf")
    assert child_document is not None
    assert child_document.format == "pdf"
    assert child_document.meta is not None
    assert child_document.meta["discovery"]["parent_document_id"] == str(catalog_doc["document_id"])
