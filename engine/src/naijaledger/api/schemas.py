"""Public response DTOs for the read API (spec 0023)."""

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    limit: int
    offset: int
    count: int


class PublicSource(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    url: str
    jurisdiction: str
    region: str | None
    category: str
    format: str
    fetch_method: str
    status: str
    health_status: str
    expected_cadence: float | None = Field(
        description="Cadence in seconds, or null when unset",
    )
    created_at: datetime
    updated_at: datetime


class PublicParty(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    party_type: str
    canonical_name: str
    aliases: list[str]
    merged_into_id: UUID | None
    created_at: datetime
    updated_at: datetime


class PublicTender(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ocid: str | None
    agency_id: UUID
    title: str
    method: str | None
    value_amount: int | None
    currency: str
    bidding_opens_at: datetime | None
    bidding_closes_at: datetime | None
    state_code: str | None = None
    lga: str | None = None
    fiscal_year: int | None = None
    created_at: datetime
    updated_at: datetime


class PublicFacets(BaseModel):
    """Distinct facet values for Explore drill-down (spec 0034)."""

    states: list[dict[str, str]]
    years: list[int]
    lgas: list[str]


class PublicMapState(BaseModel):
    """Per-state map aggregates (spec 0035). contract_volume is tender value sum in kobo."""

    id: str
    name: str
    lat: float
    lng: float
    contract_volume: int
    tender_count: int
    open_flag_count: int
    anomaly_density: float


class PublicGraphNode(BaseModel):
    id: str
    labels: list[str]
    name: str
    kind: Literal["party", "tender", "award", "contract"]


class PublicGraphLink(BaseModel):
    id: str
    source: str
    target: str
    rel_type: str


class PublicGraphDocument(BaseModel):
    """Live Memgraph subgraph (spec 0036). available=false when Bolt unreachable."""

    id: str
    title: str
    demo: bool = False
    available: bool = True
    nodes: list[PublicGraphNode]
    links: list[PublicGraphLink]


class PublicAward(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tender_id: UUID
    supplier_id: UUID
    value_amount: int | None
    currency: str
    awarded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PublicContract(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    award_id: UUID | None
    supplier_id: UUID
    agency_id: UUID
    value_amount: int | None
    currency: str
    signed_at: datetime | None
    status: str | None
    created_at: datetime
    updated_at: datetime


class PublicFlag(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_type: str
    subject_id: UUID
    rule: str
    severity: str
    evidence: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime
