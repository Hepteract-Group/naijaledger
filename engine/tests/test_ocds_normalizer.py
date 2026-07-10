from __future__ import annotations

from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

from naijaledger.extractions.models import ExtractionCreate
from naijaledger.extractions.service import (
    create_extraction,
    list_provenance_edges_for_subject,
)
from naijaledger.finance.ocds import (
    OcdsNormalizeError,
    amount_to_kobo,
    map_procurement_method,
    normalize_ocds_document,
    normalize_ocds_release,
    unwrap_extraction_payload,
)
from naijaledger.finance.ocds_load import load_normalized_release
from naijaledger.finance.ocds_models import ProvenanceContext
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import create_source


def _sample_release() -> dict[str, Any]:
    return {
        "ocid": "ocds-test-001",
        "buyer": {"id": "buyer-1", "name": "Test Ministry"},
        "parties": [
            {
                "id": "buyer-1",
                "name": "Test Ministry",
                "roles": ["buyer"],
                "identifier": {"scheme": "NG-MDAs", "id": "TM"},
            },
            {
                "id": "supplier-1",
                "name": "Acme Supplies Ltd",
                "roles": ["supplier"],
            },
        ],
        "tender": {
            "id": "t1",
            "title": "Supply of widgets",
            "procurementMethod": "open",
            "value": {"amount": 1000.5, "currency": "NGN"},
            "tenderPeriod": {
                "startDate": "2024-01-01T00:00:00Z",
                "endDate": "2024-01-31T23:59:59Z",
            },
            "procuringEntity": {"id": "buyer-1", "name": "Test Ministry"},
        },
        "awards": [
            {
                "id": "a1",
                "date": "2024-02-15T12:00:00Z",
                "value": {"amount": 900, "currency": "NGN"},
                "suppliers": [{"id": "supplier-1", "name": "Acme Supplies Ltd"}],
            }
        ],
        "contracts": [
            {
                "id": "c1",
                "awardID": "a1",
                "status": "active",
                "dateSigned": "2024-03-01T00:00:00Z",
                "value": {"amount": 900, "currency": "NGN"},
                "period": {"startDate": "2024-03-01", "endDate": "2024-12-31"},
                "suppliers": [{"id": "supplier-1", "name": "Acme Supplies Ltd"}],
            }
        ],
    }


def _seed_extraction(db_connection) -> tuple[UUID, UUID]:
    source = create_source(
        db_connection,
        SourceCreate(
            name="OCDS Provenance Test",
            jurisdiction="federal",
            category="procurement",
            url="https://example.com/ocds.json",
            fetch_method="http",
            format="json",
            added_by=SEED_ADDED_BY,
        ),
    )
    fetch_id = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, 'ocds-prov-hash', 'sha256/ocds-prov-hash'
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
                source_id, first_fetch_id, sha256, format, archive_key
            ) VALUES (
                :source_id, :fetch_id, 'ocds-prov-hash', 'json', 'sha256/ocds-prov-hash'
            )
            RETURNING id
            """
        ),
        {"source_id": source.id, "fetch_id": fetch_id},
    ).scalar_one()
    extraction = create_extraction(
        db_connection,
        ExtractionCreate(
            document_id=document_id,
            method="json",
            method_version="stdlib-json-1",
            derivation="extracted",
            confidence=1.0,
            ok=True,
            payload={"blocks": []},
            status="parsed",
        ),
    )
    return document_id, extraction.id


def test_amount_to_kobo() -> None:
    assert amount_to_kobo(1000.5) == 100050
    assert amount_to_kobo(None) is None
    assert amount_to_kobo("not-a-number") is None


def test_map_procurement_method() -> None:
    assert map_procurement_method("open") == "open"
    assert map_procurement_method("SELECTIVE") == "selective"
    assert map_procurement_method("limited") == "limited"
    assert map_procurement_method("direct") == "direct"
    assert map_procurement_method("other") is None
    assert map_procurement_method(None) is None


def test_unwrap_extraction_payload() -> None:
    inner = {"ocid": "x"}
    assert unwrap_extraction_payload({"value": inner}) == inner
    assert unwrap_extraction_payload({"value": inner, "index": 0}) == inner
    assert unwrap_extraction_payload({"ocid": "x"}) == {"ocid": "x"}


def test_normalize_sample_release() -> None:
    release = normalize_ocds_release(_sample_release())
    assert release.ocid == "ocds-test-001"
    assert release.tender is not None
    assert release.tender.title == "Supply of widgets"
    assert release.tender.value_amount == 100050
    assert release.tender.method == "open"
    assert release.parties["buyer-1"].party_type == "agency"
    assert release.parties["supplier-1"].canonical_name == "Acme Supplies Ltd"
    assert len(release.awards) == 1
    assert release.awards[0].value_amount == 90000
    assert len(release.contracts) == 1
    assert release.contracts[0].award_ref == "a1"
    assert release.skipped == []


def test_normalize_release_package() -> None:
    package = {
        "releases": [
            {**_sample_release(), "ocid": "ocds-a"},
            {**_sample_release(), "ocid": "ocds-b"},
        ]
    }
    releases = normalize_ocds_document(package)
    assert [item.ocid for item in releases] == ["ocds-a", "ocds-b"]


def test_normalize_rejects_non_ocds() -> None:
    with pytest.raises(OcdsNormalizeError):
        normalize_ocds_document({"hello": "world"})


def test_missing_agency_skips_tender() -> None:
    release = normalize_ocds_release(
        {
            "ocid": "ocds-no-agency",
            "tender": {"title": "Orphan tender", "procurementMethod": "open"},
        }
    )
    assert release.tender is None
    assert any("agency" in reason for reason in release.skipped)


def test_load_normalized_release_idempotent_tender(db_connection) -> None:
    normalized = normalize_ocds_release(_sample_release())
    first = load_normalized_release(db_connection, normalized)
    second = load_normalized_release(db_connection, normalized)

    assert first.tender_id is not None
    assert second.tender_id == first.tender_id
    count = db_connection.execute(
        text("SELECT count(*) FROM tenders WHERE ocid = :ocid"),
        {"ocid": "ocds-test-001"},
    ).scalar_one()
    assert count == 1
    parties = db_connection.execute(text("SELECT count(*) FROM parties")).scalar_one()
    assert parties == 2


def test_load_without_provenance_creates_no_edges(db_connection) -> None:
    before = db_connection.execute(text("SELECT count(*) FROM provenance_edges")).scalar_one()
    load_normalized_release(db_connection, normalize_ocds_release(_sample_release()))
    after = db_connection.execute(text("SELECT count(*) FROM provenance_edges")).scalar_one()
    assert after == before


def test_load_with_provenance_links_subjects(db_connection) -> None:
    document_id, extraction_id = _seed_extraction(db_connection)
    ctx = ProvenanceContext(
        document_id=document_id,
        extraction_id=extraction_id,
        method="json",
        derivation="extracted",
        confidence=1.0,
    )
    normalized = normalize_ocds_release(_sample_release())
    first = load_normalized_release(db_connection, normalized, provenance=ctx)
    second = load_normalized_release(db_connection, normalized, provenance=ctx)

    assert first.tender_id is not None
    tender_edges = list_provenance_edges_for_subject(db_connection, "tender", first.tender_id)
    assert len(tender_edges) == 1
    assert tender_edges[0].document_id == document_id
    assert tender_edges[0].extraction_id == extraction_id

    assert len(first.provenance_edge_ids) >= 4  # 2 parties + tender + award + contract
    assert set(second.provenance_edge_ids) == set(first.provenance_edge_ids)
    assert second.awards_inserted == 0
    assert second.contracts_inserted == 0

    edge_count = db_connection.execute(
        text(
            """
            SELECT count(*) FROM provenance_edges
            WHERE extraction_id = :extraction_id AND subject_id IS NOT NULL
            """
        ),
        {"extraction_id": extraction_id},
    ).scalar_one()
    assert edge_count == len(first.provenance_edge_ids)
