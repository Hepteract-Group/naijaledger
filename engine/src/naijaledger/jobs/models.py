from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from naijaledger.jobs.types import JobKind, JobStatus


class Job(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: JobKind
    subject_id: UUID
    status: JobStatus
    idempotency_key: str
    run_after: datetime
    attempts: int
    max_attempts: int
    locked_at: datetime | None
    locked_by: str | None
    last_error: str | None
    result: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class EnqueueSummary(TypedDict):
    attempted: int
    inserted: int
    skipped_conflict: int
