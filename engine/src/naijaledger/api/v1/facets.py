from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.queries import list_public_facets
from naijaledger.api.schemas import PublicFacets

router = APIRouter(tags=["facets"])


@router.get("/facets", response_model=PublicFacets)
def get_facets_endpoint(
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicFacets:
    data = list_public_facets(connection)
    return PublicFacets(
        states=[{"code": s["code"], "name": s["name"]} for s in data["states"]],
        years=data["years"],
        lgas=data["lgas"],
    )
