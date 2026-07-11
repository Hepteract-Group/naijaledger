from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.queries import list_public_facets
from naijaledger.api.schemas import PublicFacets

router = APIRouter(tags=["facets"])


@router.get("/facets", response_model=PublicFacets)
def get_facets_endpoint(
    connection: Annotated[Connection, Depends(get_connection)],
    state: Annotated[
        str | None,
        Query(
            min_length=2,
            max_length=2,
            description="When set, LGAs are limited to tenders with this state_code",
        ),
    ] = None,
) -> PublicFacets:
    data = list_public_facets(connection, state=state)
    return PublicFacets(
        states=[{"code": s["code"], "name": s["name"]} for s in data["states"]],
        years=data["years"],
        lgas=data["lgas"],
    )
