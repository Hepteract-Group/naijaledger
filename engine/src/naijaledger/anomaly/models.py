from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

FlagSeverity = Literal["low", "medium", "high"]
FlagStatus = Literal["open", "dismissed", "confirmed"]


class FlagDraft(BaseModel):
    subject_type: str = Field(min_length=1)
    subject_id: UUID
    rule: str
    severity: FlagSeverity
    evidence: dict[str, Any]
    created_by: str = Field(min_length=1)

    @field_validator("evidence")
    @classmethod
    def _require_summary(cls, value: dict[str, Any]) -> dict[str, Any]:
        summary = value.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("evidence.summary must be a non-empty string")
        return value


class Flag(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    subject_type: str
    subject_id: UUID
    rule: str
    severity: FlagSeverity
    evidence: dict[str, Any]
    status: FlagStatus
    created_by: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    meta: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime
