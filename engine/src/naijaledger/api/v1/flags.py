from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Connection

from naijaledger.anomaly.service import FlagNotFoundError
from naijaledger.api.deps import get_connection
from naijaledger.api.pagination import DEFAULT_LIMIT, LimitQuery
from naijaledger.api.queries import get_public_open_flag, list_public_open_flags
from naijaledger.api.schemas import Page, PublicFlag

router = APIRouter(tags=["flags"])

_FLAG_DESCRIPTION = (
    "Anomaly flag hypothesis — not a verified claim. Only open flags are exposed."
)


@router.get(
    "/flags",
    response_model=Page[PublicFlag],
    summary="List open anomaly flags",
    description=_FLAG_DESCRIPTION,
)
def list_flags_endpoint(
    connection: Annotated[Connection, Depends(get_connection)],
    limit: LimitQuery = DEFAULT_LIMIT,
) -> Page[PublicFlag]:
    items = list_public_open_flags(connection, limit=limit)
    return Page(items=items, limit=limit, offset=0, count=len(items))


@router.get(
    "/flags/{flag_id}",
    response_model=PublicFlag,
    summary="Get an open anomaly flag",
    description=_FLAG_DESCRIPTION,
)
def get_flag_endpoint(
    flag_id: UUID,
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicFlag:
    try:
        return get_public_open_flag(connection, flag_id)
    except FlagNotFoundError as exc:
        raise HTTPException(status_code=404, detail="flag not found") from exc
