"""Review decision models (E8.3)."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ReviewDecisionKind = Literal["pending", "approve_publish", "reject", "needs_more_evidence"]
DecidedKind = Literal["approve_publish", "reject", "needs_more_evidence"]


class ReviewDecision(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_type: str
    subject_id: UUID
    decision: ReviewDecisionKind
    reviewer: str | None
    rationale: str | None
    decided_at: datetime | None
    meta: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ReviewEnqueue(BaseModel):
    subject_type: str = Field(min_length=1)
    subject_id: UUID
    meta: dict[str, Any] | None = None
