"""Flag persistence (E7.1)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import Connection, Row
from sqlalchemy.exc import NoResultFound

from naijaledger.anomaly.models import Flag, FlagDraft

_FLAG_COLUMNS = """
    id, subject_type, subject_id, rule, severity, evidence, status, created_by,
    reviewed_by, reviewed_at, meta, created_at, updated_at
"""


class FlagNotFoundError(LookupError):
    pass


class FlagStateError(ValueError):
    pass


def _row_to_flag(row: Row[Any]) -> Flag:
    mapping = row._mapping
    return Flag(
        id=mapping["id"],
        subject_type=mapping["subject_type"],
        subject_id=mapping["subject_id"],
        rule=mapping["rule"],
        severity=mapping["severity"],
        evidence=mapping["evidence"] or {},
        status=mapping["status"],
        created_by=mapping["created_by"],
        reviewed_by=mapping["reviewed_by"],
        reviewed_at=mapping["reviewed_at"],
        meta=mapping["meta"],
        created_at=mapping["created_at"],
        updated_at=mapping["updated_at"],
    )


def get_flag(connection: Connection, flag_id: UUID) -> Flag:
    try:
        row = connection.execute(
            text(f"SELECT {_FLAG_COLUMNS} FROM flags WHERE id = :id"),
            {"id": flag_id},
        ).one()
    except NoResultFound as exc:
        raise FlagNotFoundError(str(flag_id)) from exc
    return _row_to_flag(row)


def upsert_open_flag(connection: Connection, draft: FlagDraft) -> Flag | None:
    """Insert/refresh an open flag, or suppress when a sticky non-open row exists.

    Returns the open flag after insert/update, or ``None`` when a dismissed/confirmed
    row for the same (rule, subject) blocks re-open (spec 0017 sticky dismissal).
    """
    sticky = connection.execute(
        text(
            f"""
            SELECT {_FLAG_COLUMNS}
            FROM flags
            WHERE rule = :rule
              AND subject_type = :subject_type
              AND subject_id = :subject_id
              AND status IN ('dismissed', 'confirmed')
            ORDER BY updated_at DESC
            LIMIT 1
            FOR UPDATE
            """
        ),
        {
            "rule": draft.rule,
            "subject_type": draft.subject_type,
            "subject_id": draft.subject_id,
        },
    ).first()
    if sticky is not None:
        return None

    row = connection.execute(
        text(
            f"""
            INSERT INTO flags (
                subject_type, subject_id, rule, severity, evidence, status, created_by
            ) VALUES (
                :subject_type, :subject_id, :rule, :severity, CAST(:evidence AS jsonb),
                'open', :created_by
            )
            ON CONFLICT (rule, subject_type, subject_id) WHERE (status = 'open')
            DO UPDATE SET
                severity = EXCLUDED.severity,
                evidence = EXCLUDED.evidence,
                created_by = EXCLUDED.created_by,
                updated_at = now()
            RETURNING {_FLAG_COLUMNS}
            """
        ),
        {
            "subject_type": draft.subject_type,
            "subject_id": draft.subject_id,
            "rule": draft.rule,
            "severity": draft.severity,
            "evidence": json.dumps(draft.evidence),
            "created_by": draft.created_by,
        },
    ).one()
    return _row_to_flag(row)


def list_open_flags(connection: Connection, *, limit: int = 100) -> list[Flag]:
    rows = connection.execute(
        text(
            f"""
            SELECT {_FLAG_COLUMNS}
            FROM flags
            WHERE status = 'open'
            ORDER BY created_at ASC
            LIMIT :limit
            """
        ),
        {"limit": limit},
    ).all()
    return [_row_to_flag(row) for row in rows]


def dismiss_flag(connection: Connection, flag_id: UUID, *, reviewed_by: str) -> Flag:
    return _set_reviewed_status(connection, flag_id, status="dismissed", reviewed_by=reviewed_by)


def confirm_flag(connection: Connection, flag_id: UUID, *, reviewed_by: str) -> Flag:
    return _set_reviewed_status(connection, flag_id, status="confirmed", reviewed_by=reviewed_by)


def _set_reviewed_status(
    connection: Connection,
    flag_id: UUID,
    *,
    status: str,
    reviewed_by: str,
) -> Flag:
    flag = get_flag(connection, flag_id)
    if flag.status != "open":
        raise FlagStateError(f"flag is {flag.status}, not open")
    result = connection.execute(
        text(
            """
            UPDATE flags
            SET status = :status,
                reviewed_by = :reviewed_by,
                reviewed_at = now(),
                updated_at = now()
            WHERE id = :id AND status = 'open'
            """
        ),
        {"id": flag_id, "status": status, "reviewed_by": reviewed_by},
    )
    if result.rowcount != 1:
        raise FlagStateError("flag is no longer open")
    return get_flag(connection, flag_id)
