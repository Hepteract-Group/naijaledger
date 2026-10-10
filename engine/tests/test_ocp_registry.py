"""Fixture tests for OCP state bulk load (spec 0041 / #203)."""

from __future__ import annotations

import gzip
import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import httpx
from sqlalchemy import text

from naijaledger.finance.ocds import normalize_ocds_release
from naijaledger.finance.ocds_load import load_normalized_release
from naijaledger.finance.ocds_models import (
    NormalizedAward,
    NormalizedParty,
    NormalizedRelease,
    NormalizedTender,
)
from naijaledger.finance.ocp_load import LoadHooks, load_all_publications, load_publication_body
from naijaledger.finance.ocp_registry import (
    OcpPublication,
    flatten_compiled_release,
    licence_matches_record,
    parse_licence_field,
    parse_licence_record,
    prepare_release_dict,
    publication_download_url,
    publication_page_url,
)
from naijaledger.jobs.service import enqueue_due_fetch_jobs
from naijaledger.seeds.catalog import SEED_APPROVED_BY, SEED_CATALOG
from naijaledger.seeds.run import apply_seed_catalog
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source

_FIXTURES = Path(__file__).parent / "fixtures"
_LICENCE_PHRASE = "Open Data Commons Public Domain Dedication and Licence (PDDL)"


def _write_licence(tmp_path: Path, slug: str, publication_id: str) -> Path:
    path = tmp_path / f"ocp-state-{slug}.md"
    path.write_text(
        f"""# Licence record — {slug}

- **Publication URL**: https://data.open-contracting.org/en/publication/{publication_id}
- **Download URL**: https://data.open-contracting.org/en/publication/{publication_id}/download?name=full.jsonl.gz
- **Licence phrase as read**: {_LICENCE_PHRASE}
- **Date read**: 2026-10-10
- **Signed by**: human:founder-2026-10-10
""",
        encoding="utf-8",
    )
    return path


def _seed_source(db_connection, publication: OcpPublication):
    source = create_source(
        db_connection,
        SourceCreate(
            name=f"OCP {publication.state_name}",
            jurisdiction="state",
            region=publication.state_name,
            category="procurement",
            url=publication_download_url(publication.publication_id),
            fetch_method="api",
            format="json",
            expected_cadence=None,
            added_by="test",
            ingest_role="leaf",
        ),
    )
    approve_source(db_connection, source.id, approved_by="human:issue-203")
    return source


def _fake_store(monkeypatch):
    def store(minio_client, bucket, body, content_type="application/octet-stream"):
        digest = f"sha256/{len(body)}"
        return {"archive_key": digest, "content_hash": digest[7:]}

    monkeypatch.setattr("naijaledger.fetch.capture.store_raw_bytes", store)


def test_flatten_edo_required_for_supplier() -> None:
    raw = json.loads(gzip.open(_FIXTURES / "ocp_edo.jsonl.gz", "rt").readline())
    assert raw["awards"][0].get("suppliers") is None
    flat = flatten_compiled_release(raw)
    assert flat["awards"][0]["suppliers"][0]["name"] == "SOLWIN ENGINEERING COMPANY LIMITED"
    prepared = prepare_release_dict(raw)
    release = normalize_ocds_release(prepared)
    assert release.awards[0].value_amount == 18383599000
    assert "SOLWIN" in release.awards[0].supplier_ref or any(
        "SOLWIN" in p.canonical_name for p in release.parties.values()
    )


def test_parse_licence_field_ignores_nav_phrase() -> None:
    html = (_FIXTURES / "ocp_page_nav_only_pddl.html").read_text(encoding="utf-8")
    field = parse_licence_field(html)
    assert field is None or not field.strip()


def test_parse_licence_field_real_edo_page() -> None:
    html = (_FIXTURES / "ocp_page_edo_real.html").read_text(encoding="utf-8")
    field = parse_licence_field(html)
    assert field is not None
    assert "Public Domain Dedication" in field
    record = parse_licence_record(
        f"**Licence phrase as read**: {_LICENCE_PHRASE}\n"
        "**Publication URL**: https://data.open-contracting.org/en/publication/102\n"
        "**Date read**: 2026-10-10\n"
        "**Signed by**: human:test\n"
    )
    assert record is not None
    assert licence_matches_record(field, record)


def test_licence_matches_short_form() -> None:
    record = parse_licence_record(
        f"**Licence phrase as read**: {_LICENCE_PHRASE}\n"
        "**Publication URL**: https://example.test\n"
        "**Date read**: 2026-10-10\n"
        "**Signed by**: human:test\n"
    )
    assert record is not None
    assert licence_matches_record("public domain dedication (pddl)", record)


def test_load_flat_idempotent(db_connection, monkeypatch, tmp_path) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    body = (_FIXTURES / "ocp_flat.jsonl.gz").read_bytes()
    hooks = LoadHooks(events=[])
    first = load_publication_body(
        db_connection,
        source,
        pub,
        body,
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=hooks,
    )
    assert first.skip_reason == ""
    assert first.releases == 1
    assert first.awards_written == 1
    tenders = db_connection.execute(text("SELECT count(*) FROM tenders")).scalar_one()
    awards = db_connection.execute(text("SELECT count(*) FROM awards")).scalar_one()
    contracts = db_connection.execute(text("SELECT count(*) FROM contracts")).scalar_one()
    second = load_publication_body(
        db_connection,
        source,
        pub,
        body,
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert second.awards_written == 1
    assert db_connection.execute(text("SELECT count(*) FROM tenders")).scalar_one() == tenders
    assert db_connection.execute(text("SELECT count(*) FROM awards")).scalar_one() == awards
    assert db_connection.execute(text("SELECT count(*) FROM contracts")).scalar_one() == contracts


def test_load_edo_contract_and_meta(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("edo", "Edo", "102", "ED")
    source = _seed_source(db_connection, pub)
    body = (_FIXTURES / "ocp_edo.jsonl.gz").read_bytes()
    summary = load_publication_body(
        db_connection,
        source,
        pub,
        body,
        retrieved_on=date(2022, 6, 3),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert summary.awards_written == 1
    assert summary.awards_positive_amount == 1
    row = db_connection.execute(
        text(
            """
            SELECT t.state_code, t.value_amount, t.meta, a.value_amount AS award_amount,
                   p.canonical_name
            FROM tenders t
            JOIN awards a ON a.tender_id = t.id
            JOIN parties p ON p.id = a.supplier_id
            WHERE t.ocid = 'ocds-fmoaoq-edsg-dca8-00002'
            """
        )
    ).one()
    assert row.state_code == "ED"
    assert row.award_amount == 18383599000
    assert row.canonical_name == "SOLWIN ENGINEERING COMPANY LIMITED"
    assert row.meta["ocp_publication_id"] == "102"
    assert row.meta["ocp_retrieved_on"] == "2022-06-03"
    assert row.meta["source_kind"] == "ocp_registry"
    assert "Open Contracting Partnership" in row.meta["attribution"]
    contract = db_connection.execute(
        text(
            """
            SELECT c.meta->>'ocds_contract_id' AS cid,
                   c.meta->>'ocds_contract_id_raw' AS raw,
                   a.meta->>'ocds_award_id' AS award_id
            FROM contracts c
            JOIN awards a ON a.id = c.award_id
            """
        )
    ).one()
    assert contract.cid == "ocds-fmoaoq-edsg-dca8-00002:ocds-fmoaoq-edsg-dca8-00002-contract"
    assert contract.raw == "ocds-fmoaoq-edsg-dca8-00002-contract"
    assert contract.award_id == "ocds-fmoaoq-edsg-dca8-00002-award"
    second = load_publication_body(
        db_connection,
        source,
        pub,
        body,
        retrieved_on=date(2022, 6, 3),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert db_connection.execute(text("SELECT count(*) FROM awards")).scalar_one() == 1
    assert db_connection.execute(text("SELECT count(*) FROM contracts")).scalar_one() == 1
    assert second.awards_written == 1


def test_zero_amount_counted(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    summary = load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_zero.jsonl.gz").read_bytes(),
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert summary.awards_written == 1
    assert summary.awards_positive_amount == 0
    amount = db_connection.execute(text("SELECT value_amount FROM awards")).scalar_one()
    assert amount == 0


def test_missing_award_id_fallback(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    body = (_FIXTURES / "ocp_missing_award_id.jsonl.gz").read_bytes()
    load_publication_body(
        db_connection,
        source,
        pub,
        body,
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    meta = db_connection.execute(text("SELECT meta FROM awards")).scalar_one()
    assert meta["ocds_award_id"] == "ocds-test-noid-00001:award:0"
    load_publication_body(
        db_connection,
        source,
        pub,
        body,
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert db_connection.execute(text("SELECT count(*) FROM awards")).scalar_one() == 1


def test_tender_only(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    summary = load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_tender_only.jsonl.gz").read_bytes(),
        retrieved_on=date(2024, 4, 7),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert summary.releases == 1
    assert summary.awards_written == 0
    assert db_connection.execute(text("SELECT count(*) FROM tenders")).scalar_one() == 1


def test_archive_before_parse(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    hooks = LoadHooks()
    load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_flat.jsonl.gz").read_bytes(),
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=hooks,
    )
    assert hooks.events.index("archive_done") < hooks.events.index("parse_start")


def test_null_amount_preserves_stored(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("edo", "Edo", "102", "ED")
    source = _seed_source(db_connection, pub)
    load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_edo.jsonl.gz").read_bytes(),
        retrieved_on=date(2022, 6, 3),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    # second load with null tender value via prepared release path: update meta omit retrieved
    parties = {
        "a": NormalizedParty(
            party_type="agency",
            canonical_name="Directorate of Central Administration",
        ),
    }
    release = NormalizedRelease(
        ocid="ocds-fmoaoq-edsg-dca8-00002",
        parties=parties,
        tender=NormalizedTender(
            ocid="ocds-fmoaoq-edsg-dca8-00002",
            agency_ref="a",
            title="CONNECTION OF EDSG LOCATIONS",
            method="direct",
            value_amount=None,
            currency="NGN",
            state_code="ED",
            meta={"source_kind": "ocp_registry"},
        ),
        awards=[],
        contracts=[],
    )
    load_normalized_release(db_connection, release)
    row = db_connection.execute(
        text("SELECT value_amount, meta FROM tenders WHERE ocid = 'ocds-fmoaoq-edsg-dca8-00002'")
    ).one()
    assert row.value_amount == 18383599000
    assert row.meta["ocp_retrieved_on"] == "2022-06-03"


def test_live_portal_beats_archive(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("edo", "Edo", "102", "ED")
    source = _seed_source(db_connection, pub)
    load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_edo.jsonl.gz").read_bytes(),
        retrieved_on=date(2022, 6, 3),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    parties = {
        "a": NormalizedParty(
            party_type="agency",
            canonical_name="Directorate of Central Administration",
        ),
    }
    live = NormalizedRelease(
        ocid="ocds-fmoaoq-edsg-dca8-00002",
        parties=parties,
        tender=NormalizedTender(
            ocid="ocds-fmoaoq-edsg-dca8-00002",
            agency_ref="a",
            title="Live fresher title",
            method="direct",
            value_amount=9990000,
            currency="NGN",
            state_code="ED",
            meta={"source_kind": "live_portal"},
        ),
        awards=[],
        contracts=[],
    )
    load_normalized_release(db_connection, live)
    # archive reload must not overwrite
    load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_edo.jsonl.gz").read_bytes(),
        retrieved_on=date(2022, 6, 3),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    row = db_connection.execute(
        text("SELECT title, value_amount, meta FROM tenders WHERE ocid = :ocid"),
        {"ocid": "ocds-fmoaoq-edsg-dca8-00002"},
    ).one()
    assert row.title == "Live fresher title"
    assert row.value_amount == 9990000
    assert row.meta["source_kind"] == "live_portal"
    assert row.meta["ocp_retrieved_on"] == "2022-06-03"


def test_award_dedupe_ignores_supplier_string(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_flat.jsonl.gz").read_bytes(),
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    parties = {
        "a": NormalizedParty(party_type="agency", canonical_name="Test Agency"),
        "s": NormalizedParty(party_type="company", canonical_name="Flat Supplier Limited"),
    }
    release = NormalizedRelease(
        ocid="ocds-test-flat-00001",
        parties=parties,
        tender=NormalizedTender(
            ocid="ocds-test-flat-00001",
            agency_ref="a",
            title="Flat road works",
            method="open",
            value_amount=100000,
            currency="NGN",
            meta={"source_kind": "ocp_registry"},
        ),
        awards=[
            NormalizedAward(
                ocds_award_id="ocds-test-flat-00001-award",
                supplier_ref="s",
                value_amount=100000,
                currency="NGN",
                meta={"source_kind": "ocp_registry"},
            )
        ],
    )
    load_normalized_release(db_connection, release)
    assert db_connection.execute(text("SELECT count(*) FROM awards")).scalar_one() == 1


def _http_factory(pages: dict[str, tuple[int, str | bytes]]):
    def http_get(url: str, timeout: float = 30.0):
        status, body = pages[url]
        if isinstance(body, str):
            return httpx.Response(status, text=body, request=httpx.Request("GET", url))
        return httpx.Response(status, content=body, request=httpx.Request("GET", url))

    return http_get


def test_gate_no_licence_record(db_connection, monkeypatch, tmp_path) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    _seed_source(db_connection, pub)
    called: list[str] = []

    def http_get(url: str, timeout: float = 30.0):
        called.append(url)
        raise AssertionError("should not download")

    summaries = load_all_publications(
        db_connection,
        minio_client=MagicMock(),
        bucket="test",
        licences_dir=tmp_path,
        hooks=LoadHooks(http_get=http_get, sleep=lambda _: None),
        publications=(pub,),
    )
    assert summaries[0].skip_reason == "no_licence_record"
    assert called == []


def test_gate_nav_only_pddl_does_not_download(db_connection, monkeypatch, tmp_path) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    _seed_source(db_connection, pub)
    _write_licence(tmp_path, "abia", "107")
    page = publication_page_url("107")
    nav = (_FIXTURES / "ocp_page_nav_only_pddl.html").read_text(encoding="utf-8")
    called: list[str] = []

    def http_get(url: str, timeout: float = 30.0):
        called.append(url)
        if url == page:
            return httpx.Response(200, text=nav, request=httpx.Request("GET", url))
        raise AssertionError(f"unexpected download {url}")

    summaries = load_all_publications(
        db_connection,
        minio_client=MagicMock(),
        bucket="test",
        licences_dir=tmp_path,
        hooks=LoadHooks(http_get=http_get, sleep=lambda _: None),
        publications=(pub,),
    )
    assert summaries[0].skip_reason == "no_open_licence"
    assert called == [page]


def test_gate_empty_licence_and_other(db_connection, monkeypatch, tmp_path) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    _seed_source(db_connection, pub)
    _write_licence(tmp_path, "abia", "107")
    page = publication_page_url("107")
    download = publication_download_url("107")

    empty = (_FIXTURES / "ocp_page_empty_licence.html").read_text(encoding="utf-8")
    summaries = load_all_publications(
        db_connection,
        minio_client=MagicMock(),
        bucket="test",
        licences_dir=tmp_path,
        hooks=LoadHooks(
            http_get=_http_factory({page: (200, empty)}),
            sleep=lambda _: None,
        ),
        publications=(pub,),
    )
    assert summaries[0].skip_reason == "no_open_licence"

    other = (_FIXTURES / "ocp_page_other_licence.html").read_text(encoding="utf-8")
    summaries = load_all_publications(
        db_connection,
        minio_client=MagicMock(),
        bucket="test",
        licences_dir=tmp_path,
        hooks=LoadHooks(
            http_get=_http_factory({page: (200, other), download: (200, b"nope")}),
            sleep=lambda _: None,
        ),
        publications=(pub,),
    )
    assert summaries[0].skip_reason == "licence_mismatch"


def test_gate_signed_non_pddl_blocked(db_connection, monkeypatch, tmp_path) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    _seed_source(db_connection, pub)
    non_pddl_record = tmp_path / "ocp-state-abia.md"
    non_pddl_record.write_text(
        """# Licence record — abia

- **Publication URL**: https://data.open-contracting.org/en/publication/107
- **Download URL**: https://data.open-contracting.org/en/publication/107/download?name=full.jsonl.gz
- **Licence phrase as read**: Creative Commons Attribution 4.0 International
- **Date read**: 2026-10-10
- **Signed by**: human:founder-2026-10-10
""",
        encoding="utf-8",
    )
    called: list[str] = []

    def http_get(url: str, timeout: float = 30.0):
        called.append(url)
        raise AssertionError("should not download when signed record is not PDDL")

    summaries = load_all_publications(
        db_connection,
        minio_client=MagicMock(),
        bucket="test",
        licences_dir=tmp_path,
        hooks=LoadHooks(http_get=http_get, sleep=lambda _: None),
        publications=(pub,),
    )
    assert summaries[0].skip_reason == "licence_not_pddl"
    assert called == []


def test_fetch_failed_retry_and_auth_stop(db_connection, monkeypatch, tmp_path) -> None:
    _fake_store(monkeypatch)
    pubs = (
        OcpPublication("abia", "Abia", "107", "AB"),
        OcpPublication("edo", "Edo", "102", "ED"),
        OcpPublication("enugu", "Enugu", "104", "EN"),
    )
    for pub in pubs:
        _seed_source(db_connection, pub)
        _write_licence(tmp_path, pub.slug, pub.publication_id)
    pddl = (_FIXTURES / "ocp_page_pddl.html").read_text(encoding="utf-8")
    attempts: dict[str, int] = {}

    def http_get(url: str, timeout: float = 30.0):
        attempts[url] = attempts.get(url, 0) + 1
        if "download" in url and "107" in url:
            return httpx.Response(500, request=httpx.Request("GET", url))
        if url.rstrip("/").endswith("/102") and "download" not in url:
            return httpx.Response(403, request=httpx.Request("GET", url))
        return httpx.Response(200, text=pddl, request=httpx.Request("GET", url))

    summaries = load_all_publications(
        db_connection,
        minio_client=MagicMock(),
        bucket="test",
        licences_dir=tmp_path,
        hooks=LoadHooks(http_get=http_get, sleep=lambda _: None),
        publications=pubs,
    )
    assert summaries[0].skip_reason == "fetch_failed"
    assert attempts[publication_download_url("107")] == 2
    assert len(summaries) == 2
    assert summaries[1].skip_reason == "fetch_failed"
    assert summaries[1].auth_stop is True
    # Third publication must never be requested after auth stop.
    assert publication_page_url("104") not in attempts


def test_compressed_cap(db_connection, monkeypatch, tmp_path) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    _seed_source(db_connection, pub)
    _write_licence(tmp_path, "abia", "107")
    pddl = (_FIXTURES / "ocp_page_pddl.html").read_text(encoding="utf-8")
    page = publication_page_url("107")
    download = publication_download_url("107")
    huge = b"x" * (50 * 1024 * 1024 + 1)
    summaries = load_all_publications(
        db_connection,
        minio_client=MagicMock(),
        bucket="test",
        licences_dir=tmp_path,
        hooks=LoadHooks(
            http_get=_http_factory({page: (200, pddl), download: (200, huge)}),
            sleep=lambda _: None,
        ),
        publications=(pub,),
    )
    assert summaries[0].skip_reason == "fetch_failed"


def test_decompressed_cap(db_connection, monkeypatch, tmp_path) -> None:
    _fake_store(monkeypatch)
    monkeypatch.setattr("naijaledger.finance.ocp_load.MAX_DECOMPRESSED_BYTES", 50)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    summary = load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_flat.jsonl.gz").read_bytes(),
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert summary.skip_reason == "fetch_failed"


def test_single_line_too_large(db_connection, monkeypatch, tmp_path) -> None:
    """Blocker 3: over-long line hits bounded readline and fails without inflating."""
    _fake_store(monkeypatch)
    monkeypatch.setattr("naijaledger.finance.ocp_load.MAX_DECOMPRESSED_BYTES", 100)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    body = gzip.compress(b"A" * 200)
    summary = load_publication_body(
        db_connection,
        source,
        pub,
        body,
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert summary.skip_reason == "fetch_failed"


def test_corrupt_json_marks_extraction_failed(db_connection, monkeypatch) -> None:
    """Blocker 2: corrupt JSON line marks extraction failed."""
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    line1 = b'{"ocid":"ocds-test-001","id":"1","tag":["tender"],'
    line2 = b'"tender":{"id":"t1","title":"Valid"}}\n'
    valid_line = line1 + line2
    corrupt_line = b'{"ocid":"bad","broken json\n'
    body = gzip.compress(valid_line + corrupt_line)
    summary = load_publication_body(
        db_connection,
        source,
        pub,
        body,
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert summary.skip_reason == "fetch_failed"
    query = "SELECT ok, status, payload FROM extractions ORDER BY created_at DESC LIMIT 1"
    extraction_row = db_connection.execute(text(query)).one()
    assert extraction_row.ok is False
    assert extraction_row.status == "failed"
    assert "error" in extraction_row.payload


def test_short_contract_ids_do_not_collide(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    summary = load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_contract_collide.jsonl.gz").read_bytes(),
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    assert summary.skip_reason == ""
    assert summary.releases == 2
    rows = db_connection.execute(
        text(
            """
            SELECT meta->>'ocds_contract_id' AS cid,
                   meta->>'ocds_contract_id_raw' AS raw
            FROM contracts
            ORDER BY cid
            """
        )
    ).all()
    assert len(rows) == 2
    assert {r.cid for r in rows} == {
        "ocds-test-collide-a:1",
        "ocds-test-collide-b:1",
    }
    assert {r.raw for r in rows} == {"1"}


def test_provenance_region_has_ocid(db_connection, monkeypatch) -> None:
    _fake_store(monkeypatch)
    pub = OcpPublication("abia", "Abia", "107", "AB")
    source = _seed_source(db_connection, pub)
    load_publication_body(
        db_connection,
        source,
        pub,
        (_FIXTURES / "ocp_flat.jsonl.gz").read_bytes(),
        retrieved_on=date(2023, 4, 26),
        minio_client=MagicMock(),
        bucket="test",
        hooks=LoadHooks(),
    )
    region = db_connection.execute(
        text("SELECT region FROM provenance_edges WHERE subject_type = 'award' LIMIT 1")
    ).scalar_one()
    assert region["ocid"] == "ocds-test-flat-00001"
    assert region["publication_id"] == "107"


def test_seed_approved_by_and_no_enqueue(db_connection) -> None:
    apply_seed_catalog(db_connection)
    ocp_urls = {e.url for e in SEED_CATALOG if e.name.startswith("OCP Data Registry")}
    rows = db_connection.execute(
        text("SELECT url, name, approved_by, expected_cadence FROM sources WHERE url = ANY(:urls)"),
        {"urls": list(ocp_urls)},
    ).all()
    assert len(rows) == 9
    approved_count = 0
    proposed_count = 0
    for row in rows:
        assert row.expected_cadence is None
        if "Oyo" in row.name or "Plateau" in row.name:
            assert row.approved_by is None
            proposed_count += 1
        else:
            assert row.approved_by == "human:issue-203"
            approved_count += 1
    assert approved_count == 7
    assert proposed_count == 2
    july = db_connection.execute(
        text("SELECT approved_by FROM sources WHERE url LIKE '%nocopo%' OR name LIKE 'Ekiti%'")
    ).all()
    assert any(r.approved_by == SEED_APPROVED_BY for r in july)
    summary = enqueue_due_fetch_jobs(db_connection)
    ocp_source_ids = {
        str(r.id)
        for r in db_connection.execute(
            text("SELECT id FROM sources WHERE name LIKE 'OCP Data Registry%'")
        ).all()
    }
    job_subjects = {
        str(r.subject_id)
        for r in db_connection.execute(
            text("SELECT subject_id FROM jobs WHERE kind = 'fetch_source'")
        ).all()
    }
    assert ocp_source_ids.isdisjoint(job_subjects)
    assert summary["inserted"] >= 0


def test_oyo_plateau_proposed_no_download(db_connection, monkeypatch, tmp_path) -> None:
    """Non-blocking: Oyo and Plateau stay proposed and never downloaded."""
    _fake_store(monkeypatch)
    apply_seed_catalog(db_connection)
    oyo_url = "https://data.open-contracting.org/en/publication/106"
    plateau_url = "https://data.open-contracting.org/en/publication/125"
    rows = db_connection.execute(
        text("SELECT url, status FROM sources WHERE url IN (:oyo, :plateau)"),
        {"oyo": oyo_url, "plateau": plateau_url},
    ).all()
    assert len(rows) == 2
    for row in rows:
        assert row.status == "proposed"

    oyo_pub = OcpPublication("oyo", "Oyo", "106", "OY")
    plateau_pub = OcpPublication("plateau", "Plateau", "125", "PL")
    called: list[str] = []

    def http_get(url: str, timeout: float = 30.0):
        called.append(url)
        raise AssertionError(f"should not download for proposed source: {url}")

    summaries = load_all_publications(
        db_connection,
        minio_client=MagicMock(),
        bucket="test",
        licences_dir=tmp_path,
        hooks=LoadHooks(http_get=http_get, sleep=lambda _: None),
        publications=(oyo_pub, plateau_pub),
    )
    assert len(summaries) == 2
    for summary in summaries:
        assert summary.skip_reason == "no_licence_record"
    assert called == []
