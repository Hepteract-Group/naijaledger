"""Nigeria state codes + light LGA/year parsing for facets."""

from __future__ import annotations

import re

# Codes align with web/src/map/fixtures.ts ids.
STATE_NAME_TO_CODE: dict[str, str] = {
    "abia": "AB",
    "adamawa": "AD",
    "akwa ibom": "AK",
    "anambra": "AN",
    "bauchi": "BA",
    "bayelsa": "BY",
    "benue": "BE",
    "borno": "BO",
    "cross river": "CR",
    "delta": "DE",
    "ebonyi": "EB",
    "edo": "ED",
    "ekiti": "EK",
    "enugu": "EN",
    "fct": "FC",
    "federal capital territory": "FC",
    "abuja": "FC",
    "gombe": "GO",
    "imo": "IM",
    "jigawa": "JI",
    "kaduna": "KD",
    "kano": "KN",
    "katsina": "KT",
    "kebbi": "KE",
    "kogi": "KO",
    "kwara": "KW",
    "lagos": "LA",
    "nasarawa": "NA",
    "niger": "NI",
    "ogun": "OG",
    "ondo": "ON",
    "osun": "OS",
    "oyo": "OY",
    "plateau": "PL",
    "rivers": "RI",
    "sokoto": "SO",
    "taraba": "TA",
    "yobe": "YO",
    "zamfara": "ZA",
}

STATE_CODE_TO_NAME: dict[str, str] = {
    "AB": "Abia",
    "AD": "Adamawa",
    "AK": "Akwa Ibom",
    "AN": "Anambra",
    "BA": "Bauchi",
    "BY": "Bayelsa",
    "BE": "Benue",
    "BO": "Borno",
    "CR": "Cross River",
    "DE": "Delta",
    "EB": "Ebonyi",
    "ED": "Edo",
    "EK": "Ekiti",
    "EN": "Enugu",
    "FC": "FCT",
    "GO": "Gombe",
    "IM": "Imo",
    "JI": "Jigawa",
    "KD": "Kaduna",
    "KN": "Kano",
    "KT": "Katsina",
    "KE": "Kebbi",
    "KO": "Kogi",
    "KW": "Kwara",
    "LA": "Lagos",
    "NA": "Nasarawa",
    "NI": "Niger",
    "OG": "Ogun",
    "ON": "Ondo",
    "OS": "Osun",
    "OY": "Oyo",
    "PL": "Plateau",
    "RI": "Rivers",
    "SO": "Sokoto",
    "TA": "Taraba",
    "YO": "Yobe",
    "ZA": "Zamfara",
}

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
