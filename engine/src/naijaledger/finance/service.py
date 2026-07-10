import json
from typing import Any
from uuid import UUID

from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.finance.models import Party, PartyCreate

_PARTY_COLUMNS = """
    id, party_type, canonical_name, aliases, identifiers, address, merged_into_id,
    meta, created_at, updated_at
"""


class PartyNotFoundError(LookupError):
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
