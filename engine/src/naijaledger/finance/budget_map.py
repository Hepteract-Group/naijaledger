"""Map appropriation table grids → normalized budget line drafts (spec 0037)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from naijaledger.extract.docling_map import blocks_from_docling_dict
from naijaledger.finance.ocds import amount_to_kobo

_CODE_HEADERS = ("code", "vote", "head", "item code", "economic code")
_DESC_HEADERS = ("description", "particulars", "details", "item", "narrative")
_AMOUNT_HEADERS = ("amount", "allocated", "appropriation", "allocation", "naira")
_AGENCY_HEADERS = ("agency", "mda", "ministry", "department", "organisation", "organization")


class NormalizedBudgetLine(BaseModel):
    fiscal_year: int
    agency_name: str = Field(min_length=1)
    code: str = Field(min_length=1)
    description: str | None = None
    allocated_amount: int | None = None
    jurisdiction: str = "federal"
    page: int | None = None


def _norm_header(cell: str) -> str:
    return re.sub(r"\s+", " ", cell.strip().lower())


def _header_index(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    normalized = [_norm_header(h) for h in headers]
    for idx, header in enumerate(normalized):
        for candidate in candidates:
            if candidate in header:
                return idx
    return None


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index < 0 or index >= len(row):
        return ""
    return str(row[index]).strip()


def _parse_amount_cell(raw: str, *, unit_scale: int = 1) -> int | None:
    if not raw:
        return None
    cleaned = re.sub(r"[₦,\s]", "", raw)
    cleaned = cleaned.replace("NGN", "").strip()
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    kobo = amount_to_kobo(cleaned)
    if kobo is None:
        return None
    return kobo * unit_scale


def _unit_scale_from_headers(headers: list[str]) -> int:
    joined = " ".join(_norm_header(h) for h in headers)
    if "000" in joined or "thousand" in joined:
        return 1_000
    if "million" in joined or "’m" in joined or "'m" in joined:
        return 1_000_000
    return 1


def _stable_synthetic_code(*, agency: str, description: str | None, amount: int | None) -> str:
    import hashlib

    material = f"{agency}|{description or ''}|{amount or 0}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"SYN-{digest}"


def map_table_grid_to_budget_lines(
    grid: list[list[str]],
    *,
    fiscal_year: int,
    default_agency: str = "Federal Government of Nigeria",
    max_rows: int | None = None,
    page: int | None = None,
) -> list[NormalizedBudgetLine]:
    """Map a Docling-style table grid (row 0 = headers) to budget line drafts."""
    if len(grid) < 2:
        return []
    headers = [str(cell) for cell in grid[0]]
    code_i = _header_index(headers, _CODE_HEADERS)
    desc_i = _header_index(headers, _DESC_HEADERS)
    amount_i = _header_index(headers, _AMOUNT_HEADERS)
    agency_i = _header_index(headers, _AGENCY_HEADERS)
    if amount_i is None and desc_i is None and code_i is None:
        return []
    unit_scale = _unit_scale_from_headers(headers)

    lines: list[NormalizedBudgetLine] = []
    for row in grid[1:]:
        if max_rows is not None and len(lines) >= max_rows:
            break
        if not any(str(cell).strip() for cell in row):
            continue
        description = _cell(row, desc_i) or None
        agency = _cell(row, agency_i) or default_agency
        amount = _parse_amount_cell(_cell(row, amount_i), unit_scale=unit_scale)
        explicit_code = _cell(row, code_i)
        code = explicit_code or _stable_synthetic_code(
            agency=agency, description=description, amount=amount
        )
        if description is None and amount is None and not explicit_code:
            continue
        lines.append(
            NormalizedBudgetLine(
                fiscal_year=fiscal_year,
                agency_name=agency,
                code=code,
                description=description,
                allocated_amount=amount,
                page=page,
            )
        )
    return lines


def map_docling_dict_to_budget_lines(
    docling_dict: dict[str, Any],
    *,
    fiscal_year: int,
    default_agency: str = "Federal Government of Nigeria",
    max_rows: int | None = None,
) -> list[NormalizedBudgetLine]:
    lines: list[NormalizedBudgetLine] = []
    remaining = max_rows
    for block in blocks_from_docling_dict(docling_dict):
        if block["kind"] != "table":
            continue
        payload = block["payload"]
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not rows:
            continue
        grid = [[str(cell) for cell in row] for row in rows if isinstance(row, list)]
        batch = map_table_grid_to_budget_lines(
            grid,
            fiscal_year=fiscal_year,
            default_agency=default_agency,
            max_rows=remaining,
            page=block.get("page"),
        )
        lines.extend(batch)
        if remaining is not None:
            remaining -= len(batch)
            if remaining <= 0:
                break
    return lines


def infer_fiscal_year(*candidates: str | None) -> int | None:
    for candidate in candidates:
        if not candidate:
            continue
        match = re.search(r"\b(20\d{2})\b", candidate)
        if match:
            return int(match.group(1))
    return None
