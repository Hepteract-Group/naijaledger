"""Partner export API tests (spec 0025 / E9.3)."""

from __future__ import annotations

import json
from collections.abc import Generator
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.engine import Connection

from naijaledger.anomaly.models import FlagDraft
from naijaledger.anomaly.service import dismiss_flag, upsert_open_flag
from naijaledger.api.app import create_app
from naijaledger.api.deps import get_connection
from naijaledger.api.rate_limit import is_rate_limit_exempt
from naijaledger.config import Settings
from naijaledger.finance.models import PartyCreate
from naijaledger.finance.service import create_party

TOKEN = "partner-test-token-xyz"


def _client(
    db_connection: Connection,
    **settings_overrides: object,
) -> TestClient:
    settings = Settings(
        api_rate_limit_enabled=True,
        api_rate_limit_per_minute=60,
        api_partner_export_tokens=[TOKEN],
        api_partner_export_per_minute=300,
        api_cors_origins=["http://localhost:5174"],
    ).model_copy(update=settings_overrides)
    application = create_app(settings)

    def _override() -> Generator[Connection, None, None]:
        yield db_connection

    application.dependency_overrides[get_connection] = _override
    return TestClient(application)


def _auth() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


def test_export_requires_auth(db_connection: Connection) -> None:
    client = _client(db_connection)
    assert client.get("/v1/export/parties").status_code == 401
    bad = client.get("/v1/export/flags", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401


def test_export_disabled_when_no_tokens(db_connection: Connection) -> None:
    client = _client(db_connection, api_partner_export_tokens=[])
    assert client.get("/v1/export/parties", headers=_auth()).status_code == 401


def test_export_parties_ndjson_and_json(db_connection: Connection) -> None:
    create_party(
        db_connection,
        PartyCreate(party_type="agency", canonical_name="Export Agency"),
    )
    client = _client(db_connection)
    nd = client.get("/v1/export/parties", headers=_auth())
    assert nd.status_code == 200
    assert "ndjson" in nd.headers.get("content-type", "")
    lines = [json.loads(line) for line in nd.text.strip().splitlines() if line]
    assert len(lines) == 1
    assert "meta" not in lines[0]
    assert "identifiers" not in lines[0]
    assert "added_by" not in lines[0]

    js = client.get("/v1/export/parties", headers=_auth(), params={"format": "json"})
    assert js.status_code == 200
    body = js.json()
    assert "items" in body
    assert "next_cursor" in body
    assert len(body["items"]) == 1


def test_export_cursor_pagination(db_connection: Connection) -> None:
    for i in range(3):
        create_party(
            db_connection,
            PartyCreate(party_type="company", canonical_name=f"Firm {i}"),
        )
    client = _client(db_connection)
    first = client.get("/v1/export/parties", headers=_auth(), params={"limit": 2})
    assert first.status_code == 200
    cursor = first.headers.get("x-next-cursor")
    assert cursor
    ids1 = {json.loads(line)["id"] for line in first.text.strip().splitlines()}
    second = client.get(
        "/v1/export/parties",
        headers=_auth(),
        params={"limit": 2, "cursor": cursor},
    )
    assert second.status_code == 200
    ids2 = {json.loads(line)["id"] for line in second.text.strip().splitlines()}
    assert ids1.isdisjoint(ids2)
    assert len(ids1 | ids2) == 3


def test_export_invalid_cursor(db_connection: Connection) -> None:
    client = _client(db_connection)
    assert (
        client.get(
            "/v1/export/parties",
            headers=_auth(),
            params={"cursor": "not-a-cursor"},
        ).status_code
        == 422
    )


def test_export_flags_open_only(db_connection: Connection) -> None:
    open_flag = upsert_open_flag(
        db_connection,
        FlagDraft(
            subject_type="contract",
            subject_id=uuid4(),
            rule="single_bidder",
            severity="high",
            evidence={"summary": "one bidder"},
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
            evidence={"summary": "outlier"},
            created_by="system:test",
        ),
    )
    assert dismissed is not None
    dismiss_flag(db_connection, dismissed.id, reviewed_by="human:test")

    client = _client(db_connection)
    response = client.get("/v1/export/flags", headers=_auth(), params={"format": "json"})
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["items"]}
    assert str(open_flag.id) in ids
    assert str(dismissed.id) not in ids


def test_partner_rate_limit_and_export_exempt_from_ip(
    db_connection: Connection,
) -> None:
    assert is_rate_limit_exempt("/v1/export/parties")
    client = _client(db_connection, api_partner_export_per_minute=2)
    assert client.get("/v1/export/parties", headers=_auth()).status_code == 200
    assert client.get("/v1/export/parties", headers=_auth()).status_code == 200
    limited = client.get("/v1/export/parties", headers=_auth())
    assert limited.status_code == 429
    # Public IP budget still works independently.
    assert client.get("/v1/parties").status_code == 200
