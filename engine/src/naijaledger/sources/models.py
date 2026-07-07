from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from naijaledger.sources.types import (
    FetchMethod,
    HealthStatus,
    Jurisdiction,
    SourceCategory,
    SourceFormat,
    SourceStatus,
)


class SourceCreate(BaseModel):
    name: str = Field(min_length=1)
    jurisdiction: Jurisdiction
    region: str | None = None
    category: SourceCategory
    url: str = Field(min_length=1)
    fetch_method: FetchMethod
    format: SourceFormat
    expected_cadence: timedelta | None = None
    added_by: str | None = None


class SourceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    jurisdiction: Jurisdiction | None = None
    region: str | None = None
    category: SourceCategory | None = None
    url: str | None = Field(default=None, min_length=1)
    fetch_method: FetchMethod | None = None
    format: SourceFormat | None = None
    expected_cadence: timedelta | None = None
    schema_fingerprint: str | None = None
    health_status: HealthStatus | None = None
    reliability_score: Decimal | None = Field(default=None, ge=0, le=1)


class SourceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    jurisdiction: Jurisdiction
    region: str | None
    category: SourceCategory
    url: str
    fetch_method: FetchMethod
    format: SourceFormat
    expected_cadence: timedelta | None
    last_fetched_at: datetime | None
    last_success_hash: str | None
    schema_fingerprint: str | None
    health_status: HealthStatus
    reliability_score: Decimal
    status: SourceStatus
    added_by: str | None
    approved_by: str | None
    created_at: datetime
    updated_at: datetime
