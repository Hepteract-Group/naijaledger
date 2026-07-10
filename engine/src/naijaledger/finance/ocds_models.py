from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from naijaledger.extractions.types import ExtractionDerivation, ExtractionMethod
from naijaledger.finance.types import PartyType, TenderMethod


class ProvenanceContext(BaseModel):
    document_id: UUID
    extraction_id: UUID
    method: ExtractionMethod
    derivation: ExtractionDerivation
    confidence: float = Field(ge=0.0, le=1.0)
    page: int | None = None
    region: dict[str, float] | None = None


class NormalizedParty(BaseModel):
    party_type: PartyType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    identifiers: dict[str, Any] = Field(default_factory=dict)
    address: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None


class NormalizedTender(BaseModel):
    ocid: str
    agency_ref: str
    title: str
    method: TenderMethod | None
    value_amount: int | None
    currency: str = "NGN"
    bidding_opens_at: datetime | None = None
    bidding_closes_at: datetime | None = None
    meta: dict[str, Any] | None = None


class NormalizedAward(BaseModel):
    ocds_award_id: str | None
    supplier_ref: str
    value_amount: int | None
    currency: str = "NGN"
    awarded_at: datetime | None = None
    meta: dict[str, Any] | None = None


class NormalizedContract(BaseModel):
    ocds_contract_id: str | None
    award_ref: str | None
    supplier_ref: str
    agency_ref: str
    value_amount: int | None
    currency: str = "NGN"
    signed_at: datetime | None = None
    period: dict[str, Any] | None = None
    status: str | None = None
    meta: dict[str, Any] | None = None


class NormalizedRelease(BaseModel):
    ocid: str
    parties: dict[str, NormalizedParty]
    tender: NormalizedTender | None
    awards: list[NormalizedAward] = Field(default_factory=list)
    contracts: list[NormalizedContract] = Field(default_factory=list)
    skipped: list[str] = Field(default_factory=list)


class LoadResult(BaseModel):
    tender_id: UUID | None = None
    party_ids: dict[str, UUID] = Field(default_factory=dict)
    award_ids: list[UUID] = Field(default_factory=list)
    contract_ids: list[UUID] = Field(default_factory=list)
    provenance_edge_ids: list[UUID] = Field(default_factory=list)
    parties_upserted: int = 0
    tenders_upserted: int = 0
    awards_inserted: int = 0
    contracts_inserted: int = 0
