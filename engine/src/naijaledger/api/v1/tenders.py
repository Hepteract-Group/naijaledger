from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.pagination import DEFAULT_LIMIT, LimitQuery, OffsetQuery
from naijaledger.api.queries import TenderNotFoundError, get_public_tender, list_public_tenders
from naijaledger.api.schemas import Page, PublicTender

router = APIRouter(tags=["tenders"])


@router.get("/tenders", response_model=Page[PublicTender])
def list_tenders_endpoint(
    connection: Annotated[Connection, Depends(get_connection)],
    limit: LimitQuery = DEFAULT_LIMIT,
    offset: OffsetQuery = 0,
    state: Annotated[str | None, Query(description="Two-letter state code, e.g. EK")] = None,
    lga: Annotated[str | None, Query(description="LGA name contains (ILIKE)")] = None,
    year: Annotated[int | None, Query(ge=1900, le=2100, description="Fiscal year")] = None,
) -> Page[PublicTender]:
    items = list_public_tenders(
        connection,
        limit=limit,
        offset=offset,
        state=state,
        lga=lga,
        year=year,
    )
    return Page(items=items, limit=limit, offset=offset, count=len(items))


@router.get("/tenders/{tender_id}", response_model=PublicTender)
def get_tender_endpoint(
    tender_id: UUID,
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicTender:
    try:
        return get_public_tender(connection, tender_id)
    except TenderNotFoundError as exc:
        raise HTTPException(status_code=404, detail="tender not found") from exc
