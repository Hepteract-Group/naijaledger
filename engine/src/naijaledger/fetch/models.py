from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class FetchRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    url: str
    requested_at: datetime
    status_code: int | None
    ok: bool
    byte_count: int | None
    sha256: str | None
    headers: dict[str, Any] | None
    error: str | None
    archive_key: str | None
    created_at: datetime
    updated_at: datetime
