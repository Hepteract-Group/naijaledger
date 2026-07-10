"""Pure helpers shared by red-flag rules."""

from __future__ import annotations

from datetime import datetime
from statistics import median
from typing import Any
from uuid import UUID


def as_uuid(value: Any) -> UUID | None:
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def is_ngn(currency: Any) -> bool:
    if currency is None:
        return False
    return str(currency).strip().upper() == "NGN"


def as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return None


def as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def ngn_to_kobo(ngn: int) -> int:
    return ngn * 100


def address_key(address: Any) -> str | None:
    if not isinstance(address, dict):
        return None
    street = _first_str(address, ("street", "streetAddress", "street_address"))
    city = _first_str(address, ("city", "locality"))
    if not street or not city:
        return None
    postal = _first_str(address, ("postalCode", "postcode", "postal_code")) or ""
    return f"{street}|{city}|{postal}"


def _first_str(mapping: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        raw = mapping.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip().lower()
    return None


def median_abs_deviation(values: list[int]) -> tuple[float, float]:
    """Return (median, MAD). MAD is median of absolute deviations from median."""
    med = float(median(values))
    mad = float(median([abs(v - med) for v in values]))
    return med, mad
