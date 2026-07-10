from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.engine import Connection

from naijaledger.api.deps import get_connection
from naijaledger.api.queries import ContractNotFoundError, get_public_contract
from naijaledger.api.schemas import PublicContract

router = APIRouter(tags=["contracts"])


@router.get("/contracts/{contract_id}", response_model=PublicContract)
def get_contract_endpoint(
    contract_id: UUID,
    connection: Annotated[Connection, Depends(get_connection)],
) -> PublicContract:
    try:
        return get_public_contract(connection, contract_id)
    except ContractNotFoundError as exc:
        raise HTTPException(status_code=404, detail="contract not found") from exc
