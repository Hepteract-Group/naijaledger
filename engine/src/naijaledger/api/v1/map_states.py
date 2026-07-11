from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.queries import list_public_map_states
from naijaledger.api.schemas import Page, PublicMapState

router = APIRouter(tags=["map"])

_MAP_DESCRIPTION = (
    "Per-state map aggregates. contract_volume is the sum of tender value_amount "
    "(kobo) for tenders with that state_code — a tender-value proxy, not contracts-table "
    "totals. anomaly_density is open tender-flag hypotheses / tender count "
    "(not verified wrongdoing)."
)


@router.get(
    "/map/states",
    response_model=Page[PublicMapState],
    summary="List state map aggregates",
    description=_MAP_DESCRIPTION,
)
def list_map_states_endpoint(
    connection: Annotated[Connection, Depends(get_connection)],
    year: Annotated[int | None, Query(ge=1900, le=2100)] = None,
) -> Page[PublicMapState]:
    items = list_public_map_states(connection, year=year)
    return Page(items=items, limit=len(items), offset=0, count=len(items))
