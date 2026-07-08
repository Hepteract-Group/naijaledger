from datetime import datetime
from typing import Any, TypedDict
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from naijaledger.sources.types import SourceFormat


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    first_fetch_id: UUID
    sha256: str
    format: SourceFormat
    archive_key: str
    title: str | None
    published_at: datetime | None
    meta: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DocumentUpsertResult(TypedDict):
    document_id: UUID
    created: bool
