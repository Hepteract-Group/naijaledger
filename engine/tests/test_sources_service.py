from datetime import timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from naijaledger.sources.errors import InvalidSourceTransitionError, SourceNotFoundError
from naijaledger.sources.models import SourceCreate, SourceUpdate
from naijaledger.sources.service import (
    approve_source,
    create_source,
    get_source,
    list_sources,
    record_fetch_success,
    retire_source,
    update_source,
)

_DEFAULT_SOURCE = SourceCreate(
    name="NOCOPO",
    jurisdiction="federal",
    category="procurement",
    url="https://nocopo.bpp.gov.ng/",
    fetch_method="http",
    format="html",
    expected_cadence=timedelta(days=1),
    added_by="agent:discovery",
)


def _sample_create(**overrides: object) -> SourceCreate:
    return _DEFAULT_SOURCE.model_copy(update=overrides)


def test_create_and_get_source(db_connection) -> None:
    created = create_source(db_connection, _sample_create())
    assert created.status == "proposed"
    assert created.health_status == "unknown"
    assert created.reliability_score == Decimal("0")

    fetched = get_source(db_connection, created.id)
    assert fetched.id == created.id
    assert fetched.name == "NOCOPO"


def test_create_duplicate_url_format_raises(db_connection) -> None:
    create_source(db_connection, _sample_create())
    with pytest.raises(ValueError, match="already exists"):
        create_source(db_connection, _sample_create(name="NOCOPO duplicate"))


def test_get_missing_source_raises(db_connection) -> None:
    with pytest.raises(SourceNotFoundError):
        get_source(db_connection, UUID("00000000-0000-0000-0000-000000000001"))


def test_list_sources_filters(db_connection) -> None:
    first = create_source(db_connection, _sample_create())
    second = create_source(
        db_connection,
        _sample_create(
            name="Open Treasury",
            category="payments",
            url="https://payment.gov.ng/",
        ),
    )
    approve_source(db_connection, second.id, approved_by="human:founder")

    proposed = list_sources(db_connection, status="proposed")
    assert {row.id for row in proposed} == {first.id}

    approved = list_sources(db_connection, status="approved", category="payments")
    assert [row.id for row in approved] == [second.id]


def test_update_source(db_connection) -> None:
    created = create_source(db_connection, _sample_create())
    updated = update_source(
        db_connection,
        created.id,
        SourceUpdate(name="NOCOPO Portal", reliability_score=Decimal("0.5")),
    )
    assert updated.name == "NOCOPO Portal"
    assert updated.reliability_score == Decimal("0.500")


def test_update_retired_source_rejected(db_connection) -> None:
    created = create_source(db_connection, _sample_create())
    retire_source(db_connection, created.id)
    with pytest.raises(InvalidSourceTransitionError):
        update_source(db_connection, created.id, SourceUpdate(name="blocked"))


def test_approve_source_lifecycle(db_connection) -> None:
    created = create_source(db_connection, _sample_create())
    approved = approve_source(db_connection, created.id, approved_by="human:founder")
    assert approved.status == "approved"
    assert approved.approved_by == "human:founder"

    with pytest.raises(InvalidSourceTransitionError):
        approve_source(db_connection, created.id, approved_by="human:founder")


def test_retire_source(db_connection) -> None:
    created = create_source(db_connection, _sample_create())
    approved = approve_source(db_connection, created.id, approved_by="human:founder")
    retired = retire_source(db_connection, approved.id)
    assert retired.status == "retired"

    with pytest.raises(InvalidSourceTransitionError):
        retire_source(db_connection, approved.id)


def test_record_fetch_success(db_connection) -> None:
    from datetime import UTC, datetime

    created = create_source(db_connection, _sample_create())
    fetched_at = datetime(2026, 7, 7, 12, 0, tzinfo=UTC)
    updated = record_fetch_success(
        db_connection,
        created.id,
        fetched_at=fetched_at,
        content_hash="abc123",
    )
    assert updated.last_fetched_at == fetched_at
    assert updated.last_success_hash == "abc123"
