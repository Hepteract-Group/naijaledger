from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from naijaledger.archive.types import ArchiveStoreResult
from naijaledger.fetch.playwright_fetch import (
    PlaywrightPageResult,
    dismiss_nocopo_license_modal,
    fetch_url_with_playwright,
    playwright_fetch_options,
    playwright_fetch_source,
)
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source, get_source


class _FakeLocator:
    def __init__(self, count: int) -> None:
        self._count = count

    def count(self) -> int:
        return self._count

    @property
    def first(self) -> "_FakeLocator":
        return self

    def click(self) -> None:
        return None


class _FakePage:
    def __init__(self, *, modal_present: bool) -> None:
        self._modal_present = modal_present
        self.clicked = False

    def locator(self, selector: str) -> _FakeLocator:
        if not self._modal_present:
            return _FakeLocator(0)
        if "adroitAlert" in selector:
            return _FakeLocator(1)
        return _FakeLocator(0)


def test_dismiss_nocopo_license_modal_clicks_close() -> None:
    page = _FakePage(modal_present=True)
    dismiss_nocopo_license_modal(page)
    assert page.locator("#adroitAlert .btn-close").count() == 1


def test_playwright_fetch_options_for_nocopo_includes_page_action() -> None:
    from naijaledger.config import Settings

    options = playwright_fetch_options(
        "https://nocopo.bpp.gov.ng/Open-Data",
        settings=Settings(),
    )
    assert options["page_action"] is dismiss_nocopo_license_modal


def test_playwright_fetch_options_for_gombe_waits_longer() -> None:
    from naijaledger.config import Settings

    options = playwright_fetch_options(
        "https://project.dueprocess.gm.gov.ng/projects",
        settings=Settings(),
    )
    assert options["wait"] >= 3000
    assert "page_action" not in options


def test_fetch_url_with_playwright_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeResponse:
        status = 200
        body = b"<html>Gombe Ongoing Projects LGA Completed</html>"
        text = None
        encoding = "utf-8"
        headers = {"content-type": "text/html; charset=utf-8"}

    class _FakeDynamicFetcher:
        @classmethod
        def fetch(cls, url: str, **kwargs: object) -> _FakeResponse:
            assert url == "https://project.dueprocess.gm.gov.ng/projects"
            assert kwargs.get("network_idle") is True
            return _FakeResponse()

    import scrapling.fetchers as fetchers_mod

    monkeypatch.setattr(fetchers_mod, "DynamicFetcher", _FakeDynamicFetcher)

    result = fetch_url_with_playwright("https://project.dueprocess.gm.gov.ng/projects")
    assert result["error"] is None
    assert result["status_code"] == 200
    assert b"Ongoing Projects" in (result["body"] or b"")


def test_playwright_fetch_source_success(db_connection, monkeypatch: pytest.MonkeyPatch) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Gombe State Due Process Portal",
            jurisdiction="state",
            region="Gombe",
            category="procurement",
            url="https://project.dueprocess.gm.gov.ng/projects",
            fetch_method="playwright",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")
    minio_client = MagicMock()

    def fake_playwright(_url: str, *, settings: object = None) -> PlaywrightPageResult:
        return PlaywrightPageResult(
            status_code=200,
            body=b"<html>Gombe State Ongoing Projects LGA</html>",
            headers={"content-type": "text/html"},
            error=None,
        )

    def fake_store(
        _client: object,
        _bucket: str,
        data: bytes,
        **kwargs: object,
    ) -> ArchiveStoreResult:
        return ArchiveStoreResult(
            archive_key="sha256/gombe",
            content_hash="gombe",
            byte_count=len(data),
            created=True,
        )

    monkeypatch.setattr(
        "naijaledger.fetch.playwright_fetch.fetch_url_with_playwright",
        fake_playwright,
    )
    monkeypatch.setattr("naijaledger.fetch.capture.store_raw_bytes", fake_store)

    result = playwright_fetch_source(
        db_connection,
        approved,
        minio_client=minio_client,
        bucket="test-bucket",
        requested_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
    )

    assert result["ok"] is True
    assert result["document_id"] is not None
    assert b"Ongoing Projects" in b"<html>Gombe State Ongoing Projects LGA</html>"
    updated = get_source(db_connection, approved.id)
    assert updated.last_success_hash == "gombe"


def test_playwright_fetch_source_rejects_scrapling_method(db_connection) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Scrapling only",
            jurisdiction="federal",
            category="budget",
            url="https://example.com/budget",
            fetch_method="scrapling",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")

    with pytest.raises(ValueError, match="playwright fetch only supports"):
        playwright_fetch_source(
            db_connection,
            approved,
            minio_client=MagicMock(),
            bucket="test-bucket",
        )


def test_nocopo_playwright_fetch_archives_ocid_markers(
    db_connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Nigeria Open Contracting Portal (NOCOPO) — Open Data",
            jurisdiction="federal",
            category="procurement",
            url="https://nocopo.bpp.gov.ng/Open-Data",
            fetch_method="playwright",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approved = approve_source(db_connection, source.id, approved_by="test")

    nocopo_html = b"<table><tr><th>OCID</th><td>ocds-ng-bpp-001</td><td>Download</td></tr></table>"

    def fake_playwright(_url: str, *, settings: object = None) -> PlaywrightPageResult:
        return PlaywrightPageResult(
            status_code=200,
            body=nocopo_html,
            headers={"content-type": "text/html"},
            error=None,
        )

    def fake_store(
        _client: object,
        _bucket: str,
        data: bytes,
        **kwargs: object,
    ) -> ArchiveStoreResult:
        assert b"OCID" in data
        return ArchiveStoreResult(
            archive_key="sha256/nocopo",
            content_hash="nocopo",
            byte_count=len(data),
            created=True,
        )

    monkeypatch.setattr(
        "naijaledger.fetch.playwright_fetch.fetch_url_with_playwright",
        fake_playwright,
    )
    monkeypatch.setattr("naijaledger.fetch.capture.store_raw_bytes", fake_store)

    result = playwright_fetch_source(
        db_connection,
        approved,
        minio_client=MagicMock(),
        bucket="test-bucket",
        requested_at=datetime(2026, 7, 8, 12, 0, tzinfo=UTC),
    )

    assert result["ok"] is True
    assert result["document_id"] is not None
