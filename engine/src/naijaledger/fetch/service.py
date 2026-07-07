import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.fetch.errors import FetchRecordNotFoundError
from naijaledger.fetch.models import FetchRecord

_FETCH_COLUMNS = """
    id, source_id, url, requested_at, status_code, ok, byte_count, sha256,
    headers, error, archive_key, created_at, updated_at
"""


def _row_to_record(row: Row[Any]) -> FetchRecord:
    mapping = row._mapping
    return FetchRecord(
        id=mapping["id"],
        source_id=mapping["source_id"],
        url=mapping["url"],
        requested_at=mapping["requested_at"],
        status_code=mapping["status_code"],
        ok=mapping["ok"],
        byte_count=mapping["byte_count"],
        sha256=mapping["sha256"],
        headers=mapping["headers"],
        error=mapping["error"],
        archive_key=mapping["archive_key"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def create_fetch_record(
    connection: Connection,
    *,
    source_id: UUID,
    url: str,
    requested_at: datetime,
    status_code: int | None,
    ok: bool,
    byte_count: int | None,
    sha256: str | None,
    headers: dict[str, str] | None,
    error: str | None,
    archive_key: str | None,
) -> FetchRecord:
    query = text(
        f"""
        INSERT INTO fetch_records (
            source_id, url, requested_at, status_code, ok, byte_count, sha256,
            headers, error, archive_key
        ) VALUES (
            :source_id, :url, :requested_at, :status_code, :ok, :byte_count, :sha256,
            CAST(:headers AS jsonb), :error, :archive_key
        )
        RETURNING {_FETCH_COLUMNS}
        """
    )
    row = connection.execute(
        query,
        {
            "source_id": source_id,
            "url": url,
            "requested_at": requested_at,
            "status_code": status_code,
            "ok": ok,
            "byte_count": byte_count,
            "sha256": sha256,
            "headers": json.dumps(headers) if headers is not None else None,
            "error": error,
            "archive_key": archive_key,
        },
    ).one()
    return _row_to_record(row)


def get_fetch_record(connection: Connection, fetch_id: UUID) -> FetchRecord:
    query = text(
        f"""
        SELECT {_FETCH_COLUMNS}
        FROM fetch_records
        WHERE id = :id
        """
    )
    try:
        row = connection.execute(query, {"id": fetch_id}).one()
    except NoResultFound as exc:
        raise FetchRecordNotFoundError(str(fetch_id)) from exc
    return _row_to_record(row)
