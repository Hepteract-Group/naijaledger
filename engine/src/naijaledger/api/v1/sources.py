from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.pagination import DEFAULT_LIMIT, LimitQuery, OffsetQuery
from naijaledger.api.queries import get_public_source, list_public_sources
from naijaledger.api.schemas import Page, PublicSource
from naijaledger.sources.errors import SourceNotFoundError
from naijaledger.sources.types import SourceStatus

router = APIRouter(tags=["sources"])

SourceStatusFilter = Literal["approved", "proposed", "retired", "all"]


@router.get("/sources", response_model=Page[PublicSource])
def list_sources_endpoint(
    connection: Annotated[Connection, Depends(get_connection)],
    status: Annotated[SourceStatusFilter, Query()] = "approved",
    state: Annotated[str | None, Query(description="State code or name matched to region")] = None,
    limit: LimitQuery = DEFAULT_LIMIT,
    offset: OffsetQuery = 0,
) -> Page[PublicSource]:
    status_filter: SourceStatus | None = None if status == "all" else status
    items = list_public_sources(
        connection,
        status=status_filter,
        state=state,
        limit=limit,
        offset=offset,
    )
    return Page(items=items, limit=limit, offset=offset, count=len(items))


@router.get("/sources/{source_id}", response_model=PublicSource)
def get_source_endpoint(
    source_id: UUID,
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicSource:
    try:
        return get_public_source(connection, source_id)
    except SourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="source not found") from exc
