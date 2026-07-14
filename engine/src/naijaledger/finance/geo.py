"""Nigeria state codes + light LGA/year parsing for facets."""

from __future__ import annotations

import re

from naijaledger.geo_data import build_state_code_to_name, build_state_name_to_code

# Codes/names from naijaledger/geo/nigeria_states.json (SSO with web map).
STATE_NAME_TO_CODE: dict[str, str] = build_state_name_to_code()
STATE_CODE_TO_NAME: dict[str, str] = build_state_code_to_name()

_YEAR = re.compile(r"^(19|20)\d{2}$")


def normalize_state_code(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    upper = text.upper()
    if len(upper) == 2 and upper in STATE_CODE_TO_NAME:
        return upper
    key = re.sub(r"\s+", " ", text.lower().replace("-", " ")).strip()
    key = re.sub(r"\bstate\b", "", key).strip()
    return STATE_NAME_TO_CODE.get(key)


def state_name_for_code(code: str) -> str | None:
    return STATE_CODE_TO_NAME.get(code.upper())


def normalize_lga(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = re.sub(r"\s+", " ", raw.strip())
    if not text:
        return None
    # Drop pure jurisdiction labels like "EKITI- STATE" — not an LGA.
    if re.fullmatch(r"(?i)[\w\s-]*\bstate\b", text):
        return None
    return text[:120]


def parse_fiscal_year(raw: str | None) -> int | None:
    if raw is None:
        return None
    text = raw.strip()
    if _YEAR.match(text):
        return int(text)
    return None


def list_known_state_codes() -> list[str]:
    return sorted(STATE_CODE_TO_NAME.keys())
