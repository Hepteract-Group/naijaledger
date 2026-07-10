from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from naijaledger.extractions.types import (
    ExtractionDerivation,
    ExtractionMethod,
    ExtractionStatus,
)


class ExtractionCreate(BaseModel):
    document_id: UUID
    method: ExtractionMethod
    method_version: str
    derivation: ExtractionDerivation
    confidence: float = Field(ge=0.0, le=1.0)
    ok: bool
    payload: dict[str, Any]
    content_type: str | None = None
    content_type_conf: float | None = Field(default=None, ge=0.0, le=1.0)
    status: ExtractionStatus


class Extraction(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    method: ExtractionMethod
    method_version: str
    derivation: ExtractionDerivation
    confidence: Decimal
    ok: bool
    payload: dict[str, Any]
    content_type: str | None
    content_type_conf: Decimal | None
    status: ExtractionStatus
    created_at: datetime
    updated_at: datetime


class ProvenanceEdgeCreate(BaseModel):
    document_id: UUID
    extraction_id: UUID
    method: ExtractionMethod
    derivation: ExtractionDerivation
    confidence: float = Field(ge=0.0, le=1.0)
    page: int | None = None
    region: dict[str, float] | None = None
    subject_type: str | None = None
    subject_id: UUID | None = None


class ProvenanceEdge(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_type: str | None
    subject_id: UUID | None
    document_id: UUID
    extraction_id: UUID
    page: int | None
    region: dict[str, Any] | None
    method: str
    derivation: ExtractionDerivation
    confidence: Decimal
    verified_by: str | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
