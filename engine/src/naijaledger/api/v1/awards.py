from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.queries import AwardNotFoundError, get_public_award
from naijaledger.api.schemas import PublicAward

router = APIRouter(tags=["awards"])


@router.get("/awards/{award_id}", response_model=PublicAward)
def get_award_endpoint(
    award_id: UUID,
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicAward:
    try:
        return get_public_award(connection, award_id)
    except AwardNotFoundError as exc:
        raise HTTPException(status_code=404, detail="award not found") from exc
