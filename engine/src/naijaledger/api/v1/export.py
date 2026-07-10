"""Partner bulk export routes (spec 0025)."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.engine import Connection

from naijaledger.api.auth_partner import PartnerAuth
from naijaledger.api.deps import get_connection
from naijaledger.api.export_cursor import CursorDecodeError, decode_cursor, encode_cursor
from naijaledger.api.export_queries import (
    export_awards,
    export_contracts,
    export_open_flags,
    export_parties,
    export_sources,
    export_tenders,
)
from naijaledger.sources.types import SourceStatus

router = APIRouter(prefix="/export", tags=["export"])

ExportFormat = Literal["ndjson", "json"]
ExportLimit = Annotated[int, Query(ge=1, le=2000)]
DEFAULT_EXPORT_LIMIT = 500


class ExportPage(BaseModel):
    items: list[Any]
    next_cursor: str | None


def _parse_cursor(cursor: str | None) -> Any:
    if cursor is None or cursor == "":
        return None
    try:
        return decode_cursor(cursor)
    except CursorDecodeError as exc:
        raise HTTPException(status_code=422, detail="invalid cursor") from exc


def _next_cursor(created_at: Any, row_id: UUID | None, *, page_len: int, limit: int) -> str | None:
    if row_id is None or created_at is None or page_len < limit:
        return None
    return encode_cursor(created_at=created_at, id=row_id)


def _ndjson_response(items: Sequence[BaseModel], next_cursor: str | None) -> StreamingResponse:
    def generate() -> Iterator[str]:
        for item in items:
            yield item.model_dump_json() + "\n"

    headers: dict[str, str] = {}
    if next_cursor is not None:
        headers["X-Next-Cursor"] = next_cursor
    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers=headers,
    )


def _export_response(
    items: Sequence[BaseModel],
    *,
    created_at: Any,
    row_id: UUID | None,
    limit: int,
    fmt: ExportFormat,
) -> StreamingResponse | JSONResponse:
    nxt = _next_cursor(created_at, row_id, page_len=len(items), limit=limit)
    if fmt == "json":
        body = ExportPage(items=list(items), next_cursor=nxt)
        return JSONResponse(content=body.model_dump(mode="json"))
    return _ndjson_response(items, nxt)


@router.get("/parties", response_model=None)
def export_parties_endpoint(
    _auth: PartnerAuth,
    connection: Annotated[Connection, Depends(get_connection)],
    limit: ExportLimit = DEFAULT_EXPORT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
    format: Annotated[ExportFormat, Query()] = "ndjson",
) -> StreamingResponse | JSONResponse:
    items, ts, row_id = export_parties(connection, cursor=_parse_cursor(cursor), limit=limit)
    return _export_response(items, created_at=ts, row_id=row_id, limit=limit, fmt=format)


@router.get("/tenders", response_model=None)
def export_tenders_endpoint(
    _auth: PartnerAuth,
    connection: Annotated[Connection, Depends(get_connection)],
    limit: ExportLimit = DEFAULT_EXPORT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
    format: Annotated[ExportFormat, Query()] = "ndjson",
) -> StreamingResponse | JSONResponse:
    items, ts, row_id = export_tenders(connection, cursor=_parse_cursor(cursor), limit=limit)
    return _export_response(items, created_at=ts, row_id=row_id, limit=limit, fmt=format)


@router.get("/awards", response_model=None)
def export_awards_endpoint(
    _auth: PartnerAuth,
    connection: Annotated[Connection, Depends(get_connection)],
    limit: ExportLimit = DEFAULT_EXPORT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
    format: Annotated[ExportFormat, Query()] = "ndjson",
) -> StreamingResponse | JSONResponse:
    items, ts, row_id = export_awards(connection, cursor=_parse_cursor(cursor), limit=limit)
    return _export_response(items, created_at=ts, row_id=row_id, limit=limit, fmt=format)


@router.get("/contracts", response_model=None)
def export_contracts_endpoint(
    _auth: PartnerAuth,
    connection: Annotated[Connection, Depends(get_connection)],
    limit: ExportLimit = DEFAULT_EXPORT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
    format: Annotated[ExportFormat, Query()] = "ndjson",
) -> StreamingResponse | JSONResponse:
    items, ts, row_id = export_contracts(connection, cursor=_parse_cursor(cursor), limit=limit)
    return _export_response(items, created_at=ts, row_id=row_id, limit=limit, fmt=format)


@router.get(
    "/flags",
    response_model=None,
    summary="Export open anomaly flags",
    description="Open flag hypotheses only — not verified claims.",
)
def export_flags_endpoint(
    _auth: PartnerAuth,
    connection: Annotated[Connection, Depends(get_connection)],
    limit: ExportLimit = DEFAULT_EXPORT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
    format: Annotated[ExportFormat, Query()] = "ndjson",
) -> StreamingResponse | JSONResponse:
    items, ts, row_id = export_open_flags(connection, cursor=_parse_cursor(cursor), limit=limit)
    return _export_response(items, created_at=ts, row_id=row_id, limit=limit, fmt=format)


@router.get("/sources", response_model=None)
def export_sources_endpoint(
    _auth: PartnerAuth,
    connection: Annotated[Connection, Depends(get_connection)],
    limit: ExportLimit = DEFAULT_EXPORT_LIMIT,
    cursor: Annotated[str | None, Query()] = None,
    format: Annotated[ExportFormat, Query()] = "ndjson",
    status: Annotated[Literal["approved", "proposed", "retired", "all"], Query()] = "approved",
) -> StreamingResponse | JSONResponse:
    status_filter: SourceStatus | None = None if status == "all" else status
    items, ts, row_id = export_sources(
        connection,
        cursor=_parse_cursor(cursor),
        limit=limit,
        status=status_filter,
    )
    return _export_response(items, created_at=ts, row_id=row_id, limit=limit, fmt=format)
