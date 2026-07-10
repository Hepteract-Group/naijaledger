"""Keyset SELECT helpers for partner export (spec 0025)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row

from naijaledger.api.export_cursor import CursorPayload
from naijaledger.api.queries import (
    _row_to_award,
    _row_to_contract,
    _row_to_public_party,
    _row_to_public_source,
    _row_to_tender,
)
from naijaledger.api.schemas import (
    PublicAward,
    PublicContract,
    PublicFlag,
    PublicParty,
    PublicSource,
    PublicTender,
)
from naijaledger.sources.types import SourceStatus

_PARTY_PUBLIC_COLUMNS = """
    id, party_type, canonical_name, aliases, merged_into_id, created_at, updated_at
"""
_TENDER_COLUMNS = """
    id, ocid, agency_id, title, method, value_amount, currency,
    bidding_opens_at, bidding_closes_at, created_at, updated_at
"""
_AWARD_COLUMNS = """
    id, tender_id, supplier_id, value_amount, currency, awarded_at, created_at, updated_at
"""
_CONTRACT_COLUMNS = """
    id, award_id, supplier_id, agency_id, value_amount, currency, signed_at, status,
    created_at, updated_at
"""
_SOURCE_PUBLIC_COLUMNS = """
    id, name, jurisdiction, region, category, url, fetch_method, format,
    expected_cadence, health_status, status, created_at, updated_at
"""
_FLAG_PUBLIC_COLUMNS = """
    id, subject_type, subject_id, rule, severity, evidence, status, created_at, updated_at
"""


def _row_to_public_flag(row: Row[Any]) -> PublicFlag:
    m = row._mapping
    return PublicFlag(
        id=m["id"],
        subject_type=m["subject_type"],
        subject_id=m["subject_id"],
        rule=m["rule"],
        severity=m["severity"],
        evidence=m["evidence"] or {},
        status=m["status"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
    )


def _keyset_clause(cursor: CursorPayload | None) -> tuple[str, dict[str, Any]]:
    if cursor is None:
        return "TRUE", {}
    return "(created_at, id) > (:cursor_ts, :cursor_id)", {
        "cursor_ts": cursor.t,
        "cursor_id": cursor.i,
    }


def _page(
    connection: Connection,
    *,
    sql: str,
    params: dict[str, Any],
    limit: int,
    map_row: Any,
) -> tuple[list[Any], datetime | None, UUID | None]:
    rows = connection.execute(text(sql), {**params, "limit": limit}).all()
    items = [map_row(row) for row in rows]
    if not items:
        return [], None, None
    last = items[-1]
    return items, last.created_at, last.id


def export_parties(
    connection: Connection,
    *,
    cursor: CursorPayload | None,
    limit: int,
) -> tuple[list[PublicParty], datetime | None, UUID | None]:
    where, params = _keyset_clause(cursor)
    sql = f"""
        SELECT {_PARTY_PUBLIC_COLUMNS}
        FROM parties
        WHERE {where}
        ORDER BY created_at ASC, id ASC
        LIMIT :limit
    """
    return _page(connection, sql=sql, params=params, limit=limit, map_row=_row_to_public_party)


def export_tenders(
    connection: Connection,
    *,
    cursor: CursorPayload | None,
    limit: int,
) -> tuple[list[PublicTender], datetime | None, UUID | None]:
    where, params = _keyset_clause(cursor)
    sql = f"""
        SELECT {_TENDER_COLUMNS}
        FROM tenders
        WHERE {where}
        ORDER BY created_at ASC, id ASC
        LIMIT :limit
    """
    return _page(connection, sql=sql, params=params, limit=limit, map_row=_row_to_tender)


def export_awards(
    connection: Connection,
    *,
    cursor: CursorPayload | None,
    limit: int,
) -> tuple[list[PublicAward], datetime | None, UUID | None]:
    where, params = _keyset_clause(cursor)
    sql = f"""
        SELECT {_AWARD_COLUMNS}
        FROM awards
        WHERE {where}
        ORDER BY created_at ASC, id ASC
        LIMIT :limit
    """
    return _page(connection, sql=sql, params=params, limit=limit, map_row=_row_to_award)


def export_contracts(
    connection: Connection,
    *,
    cursor: CursorPayload | None,
    limit: int,
) -> tuple[list[PublicContract], datetime | None, UUID | None]:
    where, params = _keyset_clause(cursor)
    sql = f"""
        SELECT {_CONTRACT_COLUMNS}
        FROM contracts
        WHERE {where}
        ORDER BY created_at ASC, id ASC
        LIMIT :limit
    """
    return _page(connection, sql=sql, params=params, limit=limit, map_row=_row_to_contract)


def export_open_flags(
    connection: Connection,
    *,
    cursor: CursorPayload | None,
    limit: int,
) -> tuple[list[PublicFlag], datetime | None, UUID | None]:
    where, params = _keyset_clause(cursor)
    sql = f"""
        SELECT {_FLAG_PUBLIC_COLUMNS}
        FROM flags
        WHERE status = 'open' AND ({where})
        ORDER BY created_at ASC, id ASC
        LIMIT :limit
    """
    return _page(connection, sql=sql, params=params, limit=limit, map_row=_row_to_public_flag)


def export_sources(
    connection: Connection,
    *,
    cursor: CursorPayload | None,
    limit: int,
    status: SourceStatus | None,
) -> tuple[list[PublicSource], datetime | None, UUID | None]:
    where, params = _keyset_clause(cursor)
    clauses = [f"({where})"]
    if status is not None:
        clauses.append("status = :status")
        params = {**params, "status": status}
    where_sql = " AND ".join(clauses)
    sql = f"""
        SELECT {_SOURCE_PUBLIC_COLUMNS}
        FROM sources
        WHERE {where_sql}
        ORDER BY created_at ASC, id ASC
        LIMIT :limit
    """
    return _page(connection, sql=sql, params=params, limit=limit, map_row=_row_to_public_source)
