from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text

from naijaledger.finance.ocds import (
    OcdsNormalizeError,
    amount_to_kobo,
    map_procurement_method,
    normalize_ocds_document,
    normalize_ocds_release,
    unwrap_extraction_payload,
)
from naijaledger.finance.ocds_load import load_normalized_release


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
