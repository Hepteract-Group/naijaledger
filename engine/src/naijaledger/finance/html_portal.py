"""Parse Ekiti-style OCDS portal HTML award tables into release packages."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any

_NAIRA_AMOUNT = re.compile(
    r"^[₦N]?\s*([\d,]+(?:\.\d+)?)\s*$",
    re.IGNORECASE,
)
_OCID = re.compile(r"^ocds-[a-z0-9]+-.+", re.IGNORECASE)

# Ekiti Procurements table column layout (sampled 2026-07-11).
_COL_TITLE = 1
_COL_ENTITY = 2
_COL_OCID = 3
_COL_COST = 4
_COL_CONTRACTOR = 5
_COL_AWARD_DATE = 12


class _TableExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_td = False
        self._cell = ""
        self._row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "tr":
            self._row = []
        elif tag.lower() == "td":
            self._in_td = True
            self._cell = ""

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "td" and self._in_td:
            self._in_td = False
            self._row.append(re.sub(r"\s+", " ", self._cell).strip())
        elif lowered == "tr" and self._row:
            self.rows.append(self._row)

    def handle_data(self, data: str) -> None:
        if self._in_td:
            self._cell += data


def parse_naira_amount(raw: str) -> float | None:
    cleaned = raw.strip().replace("\xa0", " ")
    match = _NAIRA_AMOUNT.match(cleaned)
    if match is None:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def parse_portal_date(raw: str) -> str | None:
    """Return ISO date (YYYY-MM-DD) from Ekiti 'Weekday, Month D, YYYY' strings."""
    text = raw.strip()
    if not text:
        return None
    for fmt in ("%A, %B %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def extract_table_rows(html: bytes) -> list[list[str]]:
    parser = _TableExtractor()
    try:
        parser.feed(html.decode("utf-8", errors="replace"))
    except Exception:
        parser.feed(html.decode("latin-1", errors="replace"))
    return parser.rows


def _party_id(prefix: str, name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "unknown"
    return f"{prefix}-{slug}"


def row_to_ocds_release(row: list[str]) -> dict[str, Any] | None:
    if len(row) <= _COL_OCID:
        return None
    ocid = row[_COL_OCID].strip()
    if not _OCID.match(ocid):
        return None
    title = row[_COL_TITLE].strip() if len(row) > _COL_TITLE else ""
    entity = row[_COL_ENTITY].strip() if len(row) > _COL_ENTITY else ""
    contractor = row[_COL_CONTRACTOR].strip() if len(row) > _COL_CONTRACTOR else ""
    cost_raw = row[_COL_COST].strip() if len(row) > _COL_COST else ""
    award_raw = row[_COL_AWARD_DATE].strip() if len(row) > _COL_AWARD_DATE else ""
    amount = parse_naira_amount(cost_raw)
    award_date = parse_portal_date(award_raw)

    buyer_id = _party_id("buyer", entity or "unknown-agency")
    supplier_id = _party_id("supplier", contractor or "unknown-supplier")
    parties: list[dict[str, Any]] = []
    if entity:
        parties.append({"id": buyer_id, "name": entity, "roles": ["buyer", "procuringEntity"]})
    if contractor:
        parties.append({"id": supplier_id, "name": contractor, "roles": ["supplier"]})

    tender: dict[str, Any] = {
        "id": ocid,
        "title": title or ocid,
        "procurementMethod": "limited",
        "procuringEntity": {"id": buyer_id, "name": entity} if entity else None,
    }
    if amount is not None:
        tender["value"] = {"amount": amount, "currency": "NGN"}

    awards: list[dict[str, Any]] = []
    if contractor:
        award: dict[str, Any] = {
            "id": f"{ocid}-award",
            "suppliers": [{"id": supplier_id, "name": contractor}],
        }
        if amount is not None:
            award["value"] = {"amount": amount, "currency": "NGN"}
        if award_date is not None:
            award["date"] = f"{award_date}T00:00:00Z"
        awards.append(award)

    release: dict[str, Any] = {
        "ocid": ocid,
        "parties": parties,
        "tender": {k: v for k, v in tender.items() if v is not None},
        "awards": awards,
        "meta": {"portal": "ekiti-html-table", "source_columns": len(row)},
    }
    if entity:
        release["buyer"] = {"id": buyer_id, "name": entity}
    return release


def ekiti_html_to_ocds_package(
    html: bytes,
    *,
    max_rows: int | None = None,
) -> dict[str, Any]:
    """Convert Ekiti Procurements HTML into an OCDS release package."""
    releases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in extract_table_rows(html):
        release = row_to_ocds_release(row)
        if release is None:
            continue
        ocid = str(release["ocid"])
        if ocid in seen:
            continue
        seen.add(ocid)
        releases.append(release)
        if max_rows is not None and len(releases) >= max_rows:
            break
    return {
        "uri": "naijaledger:ekiti-html-table",
        "version": "1.1",
        "publishedDate": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "releases": releases,
        "meta": {
            "converter": "ekiti_html_to_ocds_package",
            "release_count": len(releases),
        },
    }
