"""Public read API tests (spec 0023 / E9.1)."""

from collections.abc import Generator
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Connection

from naijaledger.anomaly.models import FlagDraft
from naijaledger.anomaly.service import dismiss_flag, upsert_open_flag
from naijaledger.api.app import app
from naijaledger.api.deps import get_connection
from naijaledger.finance.models import PartyCreate
from naijaledger.finance.service import create_party
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source


@pytest.fixture
def api_client(db_connection: Connection) -> Generator[TestClient, None, None]:
    def _override() -> Generator[Connection, None, None]:
        yield db_connection

    app.dependency_overrides[get_connection] = _override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_health_still_ok(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_parties_empty_page(api_client: TestClient) -> None:
    response = api_client.get("/v1/parties")
    assert response.status_code == 200
    body = response.json()
    assert body == {"items": [], "limit": 50, "offset": 0, "count": 0}


def test_party_not_found(api_client: TestClient) -> None:
    response = api_client.get(f"/v1/parties/{uuid4()}")
    assert response.status_code == 404


def test_party_list_and_get_excludes_sensitive_fields(
    api_client: TestClient,
    db_connection: Connection,
) -> None:
    party = create_party(
        db_connection,
        PartyCreate(
            party_type="agency",
            canonical_name="Bureau of Public Procurement",
            identifiers={"rc": "RC-1"},
            address={"city": "Abuja"},
            meta={"internal": True},
        ),
    )
    listed = api_client.get("/v1/parties")
    assert listed.status_code == 200
    body = listed.json()
    assert body["count"] == 1
    item = body["items"][0]
    assert item["id"] == str(party.id)
    assert item["canonical_name"] == "Bureau of Public Procurement"
    assert "identifiers" not in item
    assert "address" not in item
    assert "meta" not in item

    got = api_client.get(f"/v1/parties/{party.id}")
    assert got.status_code == 200
    detail = got.json()
    assert detail["id"] == str(party.id)
    assert "identifiers" not in detail
    assert "meta" not in detail


def test_sources_default_approved(
    api_client: TestClient,
    db_connection: Connection,
) -> None:
    proposed = create_source(
        db_connection,
        SourceCreate(
            name="Proposed Portal",
            jurisdiction="federal",
            category="procurement",
            url="https://example.com/proposed",
            fetch_method="http",
            format="html",
            expected_cadence=timedelta(days=1),
            added_by="test",
        ),
    )
    approved = create_source(
        db_connection,
        SourceCreate(
            name="Approved Portal",
            jurisdiction="federal",
            region="FCT",
            category="payments",
            url="https://example.com/approved",
            fetch_method="http",
            format="html",
            expected_cadence=timedelta(hours=12),
            added_by="test",
        ),
    )
    approve_source(db_connection, approved.id, approved_by="human:test")

    default = api_client.get("/v1/sources")
    assert default.status_code == 200
    ids = {row["id"] for row in default.json()["items"]}
    assert str(approved.id) in ids
    assert str(proposed.id) not in ids

    item = next(row for row in default.json()["items"] if row["id"] == str(approved.id))
    assert item["region"] == "FCT"
    assert item["expected_cadence"] == 12 * 3600
    assert "added_by" not in item
    assert "approved_by" not in item
    assert "last_success_hash" not in item


def test_flags_open_only(
    api_client: TestClient,
    db_connection: Connection,
) -> None:
    subject = uuid4()
    open_flag = upsert_open_flag(
        db_connection,
        FlagDraft(
            subject_type="contract",
            subject_id=subject,
            rule="single_bidder",
            severity="high",
            evidence={"summary": "Only one bidder"},
            created_by="system:test",
        ),
    )
    assert open_flag is not None
    dismissed = upsert_open_flag(
        db_connection,
        FlagDraft(
            subject_type="contract",
            subject_id=uuid4(),
            rule="price_outlier",
            severity="medium",
            evidence={"summary": "Price outlier"},
            created_by="system:test",
        ),
    )
    assert dismissed is not None
    dismiss_flag(db_connection, dismissed.id, reviewed_by="human:test")

    listed = api_client.get("/v1/flags")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["items"]}
    assert str(open_flag.id) in ids
    assert str(dismissed.id) not in ids
    flag_body = listed.json()["items"][0]
    assert "created_by" not in flag_body
    assert "reviewed_by" not in flag_body
    assert "meta" not in flag_body

    ok = api_client.get(f"/v1/flags/{open_flag.id}")
    assert ok.status_code == 200
    assert ok.json()["status"] == "open"

    hidden = api_client.get(f"/v1/flags/{dismissed.id}")
    assert hidden.status_code == 404


def test_tenders_awards_contracts(
    api_client: TestClient,
    db_connection: Connection,
) -> None:
    agency = create_party(
        db_connection,
        PartyCreate(party_type="agency", canonical_name="Test Agency"),
    )
    supplier = create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Test Supplier"),
    )
    tender_id = db_connection.execute(
        text(
            """
            INSERT INTO tenders (ocid, agency_id, title, method, value_amount)
            VALUES ('ocds-test-1', :agency_id, 'Road works', 'open', 1000000)
            RETURNING id
            """
        ),
        {"agency_id": agency.id},
    ).scalar_one()
    award_id = db_connection.execute(
        text(
            """
            INSERT INTO awards (tender_id, supplier_id, value_amount)
            VALUES (:tender_id, :supplier_id, 900000)
            RETURNING id
            """
        ),
        {"tender_id": tender_id, "supplier_id": supplier.id},
    ).scalar_one()
    contract_id = db_connection.execute(
        text(
            """
            INSERT INTO contracts (award_id, supplier_id, agency_id, value_amount, status)
            VALUES (:award_id, :supplier_id, :agency_id, 900000, 'active')
            RETURNING id
            """
        ),
        {
            "award_id": award_id,
            "supplier_id": supplier.id,
            "agency_id": agency.id,
        },
    ).scalar_one()

    tenders = api_client.get("/v1/tenders")
    assert tenders.status_code == 200
    assert tenders.json()["count"] == 1
    assert tenders.json()["items"][0]["title"] == "Road works"
    assert "meta" not in tenders.json()["items"][0]

    tender = api_client.get(f"/v1/tenders/{tender_id}")
    assert tender.status_code == 200
    assert tender.json()["ocid"] == "ocds-test-1"

    award = api_client.get(f"/v1/awards/{award_id}")
    assert award.status_code == 200
    assert award.json()["value_amount"] == 900000

    contract = api_client.get(f"/v1/contracts/{contract_id}")
    assert contract.status_code == 200
    assert contract.json()["status"] == "active"

    assert api_client.get(f"/v1/tenders/{uuid4()}").status_code == 404
    assert api_client.get(f"/v1/awards/{uuid4()}").status_code == 404
    assert api_client.get(f"/v1/contracts/{uuid4()}").status_code == 404


def test_v1_is_get_only(api_client: TestClient) -> None:
    for method in ("post", "put", "patch", "delete"):
        response = getattr(api_client, method)("/v1/parties")
        assert response.status_code in {405, 422}


def test_party_query_filters(
    api_client: TestClient,
    db_connection: Connection,
) -> None:
    create_party(
        db_connection,
        PartyCreate(party_type="agency", canonical_name="Lagos Ministry"),
    )
    create_party(
        db_connection,
        PartyCreate(party_type="company", canonical_name="Lagos Builders Ltd"),
    )
    filtered = api_client.get("/v1/parties", params={"party_type": "company", "q": "lagos"})
    assert filtered.status_code == 200
    items = filtered.json()["items"]
    assert len(items) == 1
    assert items[0]["party_type"] == "company"
    assert "Builders" in items[0]["canonical_name"]
