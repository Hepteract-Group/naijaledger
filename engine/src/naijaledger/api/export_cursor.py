"""Keyset cursor helpers for partner export (spec 0025)."""

from __future__ import annotations

import base64
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ValidationError


class CursorPayload(BaseModel):
    t: datetime
    i: UUID


class CursorDecodeError(ValueError):
    pass


def encode_cursor(*, created_at: datetime, id: UUID) -> str:
    raw = json.dumps(
        {"t": created_at.isoformat(), "i": str(id)},
        separators=(",", ":"),
    ).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str) -> CursorPayload:
    try:
        padding = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + padding)
        data: dict[str, Any] = json.loads(raw.decode("utf-8"))
        return CursorPayload.model_validate(data)
    except (ValueError, json.JSONDecodeError, ValidationError, UnicodeDecodeError) as exc:
        raise CursorDecodeError("invalid cursor") from exc
