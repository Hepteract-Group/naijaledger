import json
from typing import Any
from uuid import UUID

from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.finance.matching import MatchCandidate, score_party_pair
from naijaledger.finance.models import Party, PartyCreate

_PARTY_COLUMNS = """
    id, party_type, canonical_name, aliases, identifiers, address, merged_into_id,
    meta, created_at, updated_at
"""

_MAX_MERGE_DEPTH = 16


class PartyNotFoundError(LookupError):
    pass


class PartyMergeError(ValueError):
    pass


def _row_to_party(row: Row[Any]) -> Party:
    mapping = row._mapping
    return Party(
        id=mapping["id"],
        party_type=mapping["party_type"],
        canonical_name=mapping["canonical_name"],
        aliases=list(mapping["aliases"] or []),
        identifiers=mapping["identifiers"] or {},
        address=mapping["address"],
        merged_into_id=mapping["merged_into_id"],
        meta=mapping["meta"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def create_party(connection: Connection, data: PartyCreate) -> Party:
    query = text(
        f"""
        INSERT INTO parties (
            party_type, canonical_name, aliases, identifiers, address, meta
        ) VALUES (
            :party_type, :canonical_name, :aliases,
            CAST(:identifiers AS jsonb), CAST(:address AS jsonb), CAST(:meta AS jsonb)
        )
        RETURNING {_PARTY_COLUMNS}
        """
    ).bindparams(bindparam("aliases", type_=ARRAY(String())))
    row = connection.execute(
        query,
        {
            "party_type": data.party_type,
            "canonical_name": data.canonical_name,
            "aliases": data.aliases,
            "identifiers": json.dumps(data.identifiers),
            "address": json.dumps(data.address) if data.address is not None else None,
            "meta": json.dumps(data.meta) if data.meta is not None else None,
        },
    ).one()
    return _row_to_party(row)


def get_party(connection: Connection, party_id: UUID) -> Party:
    try:
        row = connection.execute(
            text(f"SELECT {_PARTY_COLUMNS} FROM parties WHERE id = :id"),
            {"id": party_id},
        ).one()
    except NoResultFound as exc:
        raise PartyNotFoundError(str(party_id)) from exc
    return _row_to_party(row)


def list_unmerged_parties_by_type(
    connection: Connection,
    party_type: str,
    *,
    exclude_id: UUID | None = None,
) -> list[Party]:
    query = text(
        f"""
        SELECT {_PARTY_COLUMNS}
        FROM parties
        WHERE party_type = :party_type
          AND merged_into_id IS NULL
          AND (:exclude_id IS NULL OR id <> :exclude_id)
        ORDER BY created_at ASC
        """
    )
    rows = connection.execute(
        query,
        {"party_type": party_type, "exclude_id": exclude_id},
    ).all()
    return [_row_to_party(row) for row in rows]


def propose_party_matches(
    connection: Connection,
    party_id: UUID,
    *,
    limit: int = 20,
) -> list[MatchCandidate]:
    party = get_party(connection, party_id)
    if party.merged_into_id is not None:
        return []
    candidates: list[MatchCandidate] = []
    for other in list_unmerged_parties_by_type(
        connection,
        party.party_type,
        exclude_id=party.id,
    ):
        match = score_party_pair(party, other)
        if match is not None:
            candidates.append(match)
    candidates.sort(key=lambda item: (-item.score, item.reason))
    return candidates[:limit]


def apply_party_merge(
    connection: Connection,
    *,
    survivor_id: UUID,
    merged_id: UUID,
) -> Party:
    if survivor_id == merged_id:
        raise PartyMergeError("cannot merge a party into itself")
    survivor = get_party(connection, survivor_id)
    merged = get_party(connection, merged_id)
    if survivor.party_type != merged.party_type:
        raise PartyMergeError("party_type mismatch")
    if survivor.merged_into_id is not None:
        raise PartyMergeError("survivor is already merged")
    if merged.merged_into_id is not None:
        raise PartyMergeError("merged party is already merged")

    aliases = list(dict.fromkeys([*survivor.aliases, *merged.aliases, merged.canonical_name]))
    identifiers = {**merged.identifiers, **survivor.identifiers}
    connection.execute(
        text(
            """
            UPDATE parties
            SET aliases = :aliases,
                identifiers = CAST(:identifiers AS jsonb),
                updated_at = now()
            WHERE id = :survivor_id
            """
        ).bindparams(bindparam("aliases", type_=ARRAY(String()))),
        {
            "survivor_id": survivor_id,
            "aliases": aliases,
            "identifiers": json.dumps(identifiers),
        },
    )
    connection.execute(
        text(
            """
            UPDATE parties
            SET merged_into_id = :survivor_id,
                updated_at = now()
            WHERE id = :merged_id
            """
        ),
        {"survivor_id": survivor_id, "merged_id": merged_id},
    )
    return get_party(connection, survivor_id)


def canonical_party_id(connection: Connection, party_id: UUID) -> UUID:
    current = party_id
    seen: set[UUID] = set()
    for _ in range(_MAX_MERGE_DEPTH):
        if current in seen:
            raise PartyMergeError(f"merge cycle detected at {current}")
        seen.add(current)
        party = get_party(connection, current)
        if party.merged_into_id is None:
            return party.id
        current = party.merged_into_id
    raise PartyMergeError("merge chain exceeds max depth")
