"""Shared pagination query params for /v1 list endpoints."""

from typing import Annotated

from fastapi import Query

LimitQuery = Annotated[int, Query(ge=1, le=200, description="Page size (max 200)")]
OffsetQuery = Annotated[int, Query(ge=0, description="Rows to skip")]

DEFAULT_LIMIT = 50
