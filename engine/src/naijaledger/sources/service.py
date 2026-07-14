from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import IntegrityError, NoResultFound

from naijaledger.sources.errors import InvalidSourceTransitionError, SourceNotFoundError
from naijaledger.sources.models import SourceCreate, SourceRecord, SourceUpdate
from naijaledger.sources.types import (
    HealthStatus,
    Jurisdiction,
    SourceCategory,
    SourceFormat,
    SourceStatus,
)

_SOURCE_COLUMNS = """
    id, name, jurisdiction, region, category, url, fetch_method, format,
    expected_cadence, last_fetched_at, last_success_hash, schema_fingerprint,
    health_status, reliability_score, status, ingest_role, added_by, approved_by,
    created_at, updated_at
"""


def _row_to_record(row: Row[Any]) -> SourceRecord:
    mapping = row._mapping
    reliability = mapping["reliability_score"]
    return SourceRecord(
        id=mapping["id"],
        name=mapping["name"],
        jurisdiction=mapping["jurisdiction"],
        region=mapping["region"],
        category=mapping["category"],
        url=mapping["url"],
        fetch_method=mapping["fetch_method"],
        format=mapping["format"],
        expected_cadence=mapping["expected_cadence"],
        last_fetched_at=mapping["last_fetched_at"],
        last_success_hash=mapping["last_success_hash"],
        schema_fingerprint=mapping["schema_fingerprint"],
        health_status=mapping["health_status"],
        reliability_score=Decimal(str(reliability)),
        status=mapping["status"],
        ingest_role=mapping["ingest_role"],
        added_by=mapping["added_by"],
        approved_by=mapping["approved_by"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def _fetch_one(connection: Connection, source_id: UUID) -> SourceRecord:
    query = text(
        f"""
        SELECT {_SOURCE_COLUMNS}
        FROM sources
        WHERE id = :id
        """
    )
    try:
        row = connection.execute(query, {"id": source_id}).one()
    except NoResultFound as exc:
        raise SourceNotFoundError(str(source_id)) from exc
    return _row_to_record(row)


def create_source(connection: Connection, data: SourceCreate) -> SourceRecord:
    query = text(
        f"""
        INSERT INTO sources (
            name, jurisdiction, region, category, url, fetch_method, format,
            expected_cadence, added_by, ingest_role
        ) VALUES (
            :name, :jurisdiction, :region, :category, :url, :fetch_method, :format,
            :expected_cadence, :added_by, :ingest_role
        )
        RETURNING {_SOURCE_COLUMNS}
        """
    )
    try:
        row = connection.execute(
            query,
            {
                "name": data.name,
                "jurisdiction": data.jurisdiction,
                "region": data.region,
                "category": data.category,
                "url": data.url,
                "fetch_method": data.fetch_method,
                "format": data.format,
                "expected_cadence": data.expected_cadence,
                "added_by": data.added_by,
                "ingest_role": data.ingest_role,
            },
        ).one()
    except IntegrityError as exc:
        raise ValueError("source with this url and format already exists") from exc
    return _row_to_record(row)


def get_source(connection: Connection, source_id: UUID) -> SourceRecord:
    return _fetch_one(connection, source_id)


def get_source_by_url_and_format(
    connection: Connection,
    url: str,
    format: SourceFormat,
) -> SourceRecord | None:
    query = text(
        f"""
        SELECT {_SOURCE_COLUMNS}
        FROM sources
        WHERE url = :url AND format = :format
        """
    )
    row = connection.execute(query, {"url": url, "format": format}).first()
    if row is None:
        return None
    return _row_to_record(row)


def list_sources(
    connection: Connection,
    *,
    status: SourceStatus | None = None,
    category: SourceCategory | None = None,
    jurisdiction: Jurisdiction | None = None,
    health_status: HealthStatus | None = None,
) -> list[SourceRecord]:
    clauses = ["1 = 1"]
    params: dict[str, Any] = {}

    if status is not None:
        clauses.append("status = :status")
        params["status"] = status
    if category is not None:
        clauses.append("category = :category")
        params["category"] = category
    if jurisdiction is not None:
        clauses.append("jurisdiction = :jurisdiction")
        params["jurisdiction"] = jurisdiction
    if health_status is not None:
        clauses.append("health_status = :health_status")
        params["health_status"] = health_status

    where_sql = " AND ".join(clauses)
    query = text(
        f"""
        SELECT {_SOURCE_COLUMNS}
        FROM sources
        WHERE {where_sql}
        ORDER BY created_at DESC
        """
    )
    rows = connection.execute(query, params).all()
    return [_row_to_record(row) for row in rows]


def update_source(
    connection: Connection,
    source_id: UUID,
    data: SourceUpdate,
) -> SourceRecord:
    current = _fetch_one(connection, source_id)
    if current.status == "retired":
        raise InvalidSourceTransitionError("retired sources cannot be updated")

    updates = data.model_dump(exclude_unset=True)
    if not updates:
        return current

    set_parts = [f"{column} = :{column}" for column in updates]
    set_parts.append("updated_at = now()")
    set_sql = ", ".join(set_parts)

    query = text(
        f"""
        UPDATE sources
        SET {set_sql}
        WHERE id = :id
        RETURNING {_SOURCE_COLUMNS}
        """
    )
    params = {"id": source_id, **updates}
    try:
        row = connection.execute(query, params).one()
    except IntegrityError as exc:
        raise ValueError("source with this url and format already exists") from exc
    return _row_to_record(row)


def approve_source(
    connection: Connection,
    source_id: UUID,
    *,
    approved_by: str,
) -> SourceRecord:
    current = _fetch_one(connection, source_id)
    if current.status != "proposed":
        raise InvalidSourceTransitionError(
            f"only proposed sources can be approved (current: {current.status})"
        )

    query = text(
        f"""
        UPDATE sources
        SET status = 'approved',
            approved_by = :approved_by,
            updated_at = now()
        WHERE id = :id
        RETURNING {_SOURCE_COLUMNS}
        """
    )
    row = connection.execute(query, {"id": source_id, "approved_by": approved_by}).one()
    return _row_to_record(row)


def demote_to_proposed(connection: Connection, source_id: UUID) -> SourceRecord:
    """Move approved → proposed (discovery/search re-scope). Not for retired."""
    current = _fetch_one(connection, source_id)
    if current.status == "retired":
        raise InvalidSourceTransitionError("retired sources cannot be demoted")
    if current.status == "proposed":
        return current

    query = text(
        f"""
        UPDATE sources
        SET status = 'proposed',
            approved_by = NULL,
            updated_at = now()
        WHERE id = :id
        RETURNING {_SOURCE_COLUMNS}
        """
    )
    row = connection.execute(query, {"id": source_id}).one()
    return _row_to_record(row)


def retire_source(connection: Connection, source_id: UUID) -> SourceRecord:
    current = _fetch_one(connection, source_id)
    if current.status == "retired":
        raise InvalidSourceTransitionError("source is already retired")

    query = text(
        f"""
        UPDATE sources
        SET status = 'retired',
            updated_at = now()
        WHERE id = :id
        RETURNING {_SOURCE_COLUMNS}
        """
    )
    row = connection.execute(query, {"id": source_id}).one()
    return _row_to_record(row)


def record_fetch_success(
    connection: Connection,
    source_id: UUID,
    *,
    fetched_at: datetime,
    content_hash: str,
) -> SourceRecord:
    _fetch_one(connection, source_id)

    query = text(
        f"""
        UPDATE sources
        SET last_fetched_at = :fetched_at,
            last_success_hash = :content_hash,
            updated_at = now()
        WHERE id = :id
        RETURNING {_SOURCE_COLUMNS}
        """
    )
    row = connection.execute(
        query,
        {"id": source_id, "fetched_at": fetched_at, "content_hash": content_hash},
    ).one()
    return _row_to_record(row)
