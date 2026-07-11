"""SELECT helpers for public read resources (spec 0023)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.anomaly.models import Flag
from naijaledger.anomaly.service import FlagNotFoundError, get_flag
from naijaledger.api.schemas import (
    PublicAward,
    PublicContract,
    PublicFlag,
    PublicMapState,
    PublicParty,
    PublicSource,
    PublicTender,
)
from naijaledger.finance.models import Party
from naijaledger.finance.service import get_party
from naijaledger.sources.models import SourceRecord
from naijaledger.sources.service import get_source
from naijaledger.sources.types import SourceStatus

_PARTY_PUBLIC_COLUMNS = """
    id, party_type, canonical_name, aliases, merged_into_id, created_at, updated_at
"""

_TENDER_COLUMNS = """
    id, ocid, agency_id, title, method, value_amount, currency,
    bidding_opens_at, bidding_closes_at, state_code, lga, fiscal_year,
    created_at, updated_at
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


class TenderNotFoundError(LookupError):
    pass


class AwardNotFoundError(LookupError):
    pass


class ContractNotFoundError(LookupError):
    pass


def _cadence_seconds(value: timedelta | None) -> float | None:
    if value is None:
        return None
    return value.total_seconds()


def to_public_source(record: SourceRecord) -> PublicSource:
    return PublicSource(
        id=record.id,
        name=record.name,
        url=record.url,
        jurisdiction=record.jurisdiction,
        region=record.region,
        category=record.category,
        format=record.format,
        fetch_method=record.fetch_method,
        status=record.status,
        health_status=record.health_status,
        expected_cadence=_cadence_seconds(record.expected_cadence),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def to_public_party(party: Party) -> PublicParty:
    return PublicParty(
        id=party.id,
        party_type=party.party_type,
        canonical_name=party.canonical_name,
        aliases=party.aliases,
        merged_into_id=party.merged_into_id,
        created_at=party.created_at,
        updated_at=party.updated_at,
    )


def to_public_flag(flag: Flag) -> PublicFlag:
    return PublicFlag(
        id=flag.id,
        subject_type=flag.subject_type,
        subject_id=flag.subject_id,
        rule=flag.rule,
        severity=flag.severity,
        evidence=flag.evidence,
        status=flag.status,
        created_at=flag.created_at,
        updated_at=flag.updated_at,
    )


def _row_to_public_source(row: Row[Any]) -> PublicSource:
    mapping = row._mapping
    return PublicSource(
        id=mapping["id"],
        name=mapping["name"],
        url=mapping["url"],
        jurisdiction=mapping["jurisdiction"],
        region=mapping["region"],
        category=mapping["category"],
        format=mapping["format"],
        fetch_method=mapping["fetch_method"],
        status=mapping["status"],
        health_status=mapping["health_status"],
        expected_cadence=_cadence_seconds(mapping["expected_cadence"]),
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def _row_to_public_party(row: Row[Any]) -> PublicParty:
    mapping = row._mapping
    return PublicParty(
        id=mapping["id"],
        party_type=mapping["party_type"],
        canonical_name=mapping["canonical_name"],
        aliases=list(mapping["aliases"] or []),
        merged_into_id=mapping["merged_into_id"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def _row_to_tender(row: Row[Any]) -> PublicTender:
    m = row._mapping
    return PublicTender(
        id=m["id"],
        ocid=m["ocid"],
        agency_id=m["agency_id"],
        title=m["title"],
        method=m["method"],
        value_amount=m["value_amount"],
        currency=m["currency"],
        bidding_opens_at=m["bidding_opens_at"],
        bidding_closes_at=m["bidding_closes_at"],
        state_code=m.get("state_code"),
        lga=m.get("lga"),
        fiscal_year=m.get("fiscal_year"),
        created_at=m["created_at"],
        updated_at=m["updated_at"],
    )


def _row_to_award(row: Row[Any]) -> PublicAward:
    m = row._mapping
    return PublicAward(
        id=m["id"],
        tender_id=m["tender_id"],
        supplier_id=m["supplier_id"],
        value_amount=m["value_amount"],
        currency=m["currency"],
        awarded_at=m["awarded_at"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
    )


def _row_to_contract(row: Row[Any]) -> PublicContract:
    m = row._mapping
    return PublicContract(
        id=m["id"],
        award_id=m["award_id"],
        supplier_id=m["supplier_id"],
        agency_id=m["agency_id"],
        value_amount=m["value_amount"],
        currency=m["currency"],
        signed_at=m["signed_at"],
        status=m["status"],
        created_at=m["created_at"],
        updated_at=m["updated_at"],
    )


def list_public_sources(
    connection: Connection,
    *,
    status: SourceStatus | None,
    limit: int,
    offset: int,
    state: str | None = None,
) -> list[PublicSource]:
    from naijaledger.finance.geo import normalize_state_code, state_name_for_code

    clauses = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if status is not None:
        clauses.append("status = :status")
        params["status"] = status
    if state is not None and state.strip():
        code = normalize_state_code(state.strip())
        if code is not None:
            name = state_name_for_code(code) or code
            # Exact code or exact region name only — avoid "Niger" matching "Nigeria".
            clauses.append("(upper(region) = :state_code OR lower(region) = lower(:state_name))")
            params["state_code"] = code
            params["state_name"] = name
    where_sql = " AND ".join(clauses)
    rows = connection.execute(
        text(
            f"""
            SELECT {_SOURCE_PUBLIC_COLUMNS}
            FROM sources
            WHERE {where_sql}
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()
    return [_row_to_public_source(row) for row in rows]


def get_public_source(connection: Connection, source_id: UUID) -> PublicSource:
    return to_public_source(get_source(connection, source_id))


def list_public_parties(
    connection: Connection,
    *,
    party_type: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> list[PublicParty]:
    clauses = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if party_type is not None:
        clauses.append("party_type = :party_type")
        params["party_type"] = party_type
    if q is not None and q.strip():
        clauses.append("canonical_name ILIKE :q")
        params["q"] = f"%{q.strip()}%"
    where_sql = " AND ".join(clauses)
    rows = connection.execute(
        text(
            f"""
            SELECT {_PARTY_PUBLIC_COLUMNS}
            FROM parties
            WHERE {where_sql}
            ORDER BY created_at ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()
    return [_row_to_public_party(row) for row in rows]


def get_public_party(connection: Connection, party_id: UUID) -> PublicParty:
    return to_public_party(get_party(connection, party_id))


def list_public_tenders(
    connection: Connection,
    *,
    limit: int,
    offset: int,
    state: str | None = None,
    lga: str | None = None,
    year: int | None = None,
) -> list[PublicTender]:
    from naijaledger.finance.geo import normalize_state_code

    clauses = ["1 = 1"]
    params: dict[str, Any] = {"limit": limit, "offset": offset}
    if state is not None and state.strip():
        code = normalize_state_code(state.strip())
        if code is not None:
            clauses.append("state_code = :state_code")
            params["state_code"] = code
    if lga is not None and lga.strip():
        clauses.append("lga ILIKE :lga")
        params["lga"] = f"%{lga.strip()}%"
    if year is not None:
        clauses.append("fiscal_year = :year")
        params["year"] = year
    where_sql = " AND ".join(clauses)
    rows = connection.execute(
        text(
            f"""
            SELECT {_TENDER_COLUMNS}
            FROM tenders
            WHERE {where_sql}
            ORDER BY created_at ASC
            LIMIT :limit OFFSET :offset
            """
        ),
        params,
    ).all()
    return [_row_to_tender(row) for row in rows]


def list_public_facets(connection: Connection) -> dict[str, Any]:
    from naijaledger.finance.geo import STATE_CODE_TO_NAME, list_known_state_codes

    used_states = {
        row[0]
        for row in connection.execute(
            text(
                """
                SELECT DISTINCT state_code FROM tenders
                WHERE state_code IS NOT NULL
                ORDER BY state_code
                """
            )
        ).all()
    }
    years = [
        int(row[0])
        for row in connection.execute(
            text(
                """
                SELECT DISTINCT fiscal_year FROM tenders
                WHERE fiscal_year IS NOT NULL
                ORDER BY fiscal_year DESC
                """
            )
        ).all()
    ]
    lgas = [
        str(row[0])
        for row in connection.execute(
            text(
                """
                SELECT DISTINCT lga FROM tenders
                WHERE lga IS NOT NULL
                ORDER BY lga
                LIMIT 200
                """
            )
        ).all()
    ]
    # Prefer known list; put states that appear in data first.
    ordered = [code for code in list_known_state_codes() if code in used_states] + [
        code for code in list_known_state_codes() if code not in used_states
    ]
    states = [{"code": code, "name": STATE_CODE_TO_NAME[code]} for code in ordered]
    return {"states": states, "years": years, "lgas": lgas}


def list_public_map_states(
    connection: Connection,
    *,
    year: int | None = None,
) -> list[PublicMapState]:
    """Centroid rows for all known states with tender/flag aggregates (spec 0035)."""
    from naijaledger.finance.centroids import STATE_CENTROIDS
    from naijaledger.finance.geo import list_known_state_codes

    year_clause = ""
    params: dict[str, Any] = {}
    if year is not None:
        year_clause = " AND fiscal_year = :year"
        params["year"] = year

    tender_rows = connection.execute(
        text(
            f"""
            SELECT state_code,
                   COALESCE(SUM(value_amount), 0) AS contract_volume,
                   COUNT(*) AS tender_count
            FROM tenders
            WHERE state_code IS NOT NULL{year_clause}
            GROUP BY state_code
            """
        ),
        params,
    ).all()
    by_code: dict[str, tuple[int, int]] = {
        str(row.state_code): (int(row.contract_volume), int(row.tender_count))
        for row in tender_rows
    }

    flag_params: dict[str, Any] = {}
    flag_year = ""
    if year is not None:
        flag_year = " AND t.fiscal_year = :year"
        flag_params["year"] = year
    flag_rows = connection.execute(
        text(
            f"""
            SELECT t.state_code, COUNT(*) AS open_flag_count
            FROM flags f
            JOIN tenders t ON t.id = f.subject_id
            WHERE f.status = 'open'
              AND f.subject_type = 'tender'
              AND t.state_code IS NOT NULL{flag_year}
            GROUP BY t.state_code
            """
        ),
        flag_params,
    ).all()
    flags_by_code = {str(row.state_code): int(row.open_flag_count) for row in flag_rows}

    states: list[PublicMapState] = []
    for code in list_known_state_codes():
        name, lat, lng = STATE_CENTROIDS[code]
        volume, tender_count = by_code.get(code, (0, 0))
        open_flags = flags_by_code.get(code, 0)
        density = (open_flags / tender_count) if tender_count > 0 else 0.0
        states.append(
            PublicMapState(
                id=code,
                name=name,
                lat=lat,
                lng=lng,
                contract_volume=volume,
                tender_count=tender_count,
                open_flag_count=open_flags,
                anomaly_density=round(density, 4),
            )
        )
    return states


def get_public_tender(connection: Connection, tender_id: UUID) -> PublicTender:
    try:
        row = connection.execute(
            text(f"SELECT {_TENDER_COLUMNS} FROM tenders WHERE id = :id"),
            {"id": tender_id},
        ).one()
    except NoResultFound as exc:
        raise TenderNotFoundError(str(tender_id)) from exc
    return _row_to_tender(row)


def get_public_award(connection: Connection, award_id: UUID) -> PublicAward:
    try:
        row = connection.execute(
            text(f"SELECT {_AWARD_COLUMNS} FROM awards WHERE id = :id"),
            {"id": award_id},
        ).one()
    except NoResultFound as exc:
        raise AwardNotFoundError(str(award_id)) from exc
    return _row_to_award(row)


def get_public_contract(connection: Connection, contract_id: UUID) -> PublicContract:
    try:
        row = connection.execute(
            text(f"SELECT {_CONTRACT_COLUMNS} FROM contracts WHERE id = :id"),
            {"id": contract_id},
        ).one()
    except NoResultFound as exc:
        raise ContractNotFoundError(str(contract_id)) from exc
    return _row_to_contract(row)


def list_public_open_flags(connection: Connection, *, limit: int) -> list[PublicFlag]:
    from naijaledger.anomaly.service import list_open_flags

    return [to_public_flag(flag) for flag in list_open_flags(connection, limit=limit)]


def get_public_open_flag(connection: Connection, flag_id: UUID) -> PublicFlag:
    flag = get_flag(connection, flag_id)
    if flag.status != "open":
        raise FlagNotFoundError(str(flag_id))
    return to_public_flag(flag)
