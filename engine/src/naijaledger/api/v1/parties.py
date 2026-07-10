from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.pagination import DEFAULT_LIMIT, LimitQuery, OffsetQuery
from naijaledger.api.queries import get_public_party, list_public_parties
from naijaledger.api.schemas import Page, PublicParty
from naijaledger.finance.service import PartyNotFoundError

router = APIRouter(tags=["parties"])

PartyTypeFilter = Literal["company", "person", "agency"]


@router.get("/parties", response_model=Page[PublicParty])
def list_parties_endpoint(
    connection: Annotated[Connection, Depends(get_connection)],
    party_type: Annotated[PartyTypeFilter | None, Query()] = None,
    q: Annotated[str | None, Query(description="ILIKE filter on canonical_name")] = None,
    limit: LimitQuery = DEFAULT_LIMIT,
    offset: OffsetQuery = 0,
) -> Page[PublicParty]:
    items = list_public_parties(
        connection,
        party_type=party_type,
        q=q,
        limit=limit,
        offset=offset,
    )
    return Page(items=items, limit=limit, offset=offset, count=len(items))


@router.get("/parties/{party_id}", response_model=PublicParty)
def get_party_endpoint(
    party_id: UUID,
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicParty:
    try:
        return get_public_party(connection, party_id)
    except PartyNotFoundError as exc:
        raise HTTPException(status_code=404, detail="party not found") from exc
