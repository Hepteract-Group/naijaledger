from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from naijaledger.finance.types import PartyType


class PartyCreate(BaseModel):
    party_type: PartyType
    canonical_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    identifiers: dict[str, Any] = Field(default_factory=dict)
    address: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


class Party(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    party_type: PartyType
    canonical_name: str
    aliases: list[str]
    identifiers: dict[str, Any]
    address: dict[str, Any] | None
    merged_into_id: UUID | None
    meta: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
