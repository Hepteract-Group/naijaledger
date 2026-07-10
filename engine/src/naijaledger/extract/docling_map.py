from typing import Any

from naijaledger.extract.outcome import Block


def _bbox_to_region(bbox: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(bbox, dict):
        return None
    try:
        left = float(bbox["l"])
        right = float(bbox["r"])
        top = float(bbox["t"])
        bottom = float(bbox["b"])
    except (KeyError, TypeError, ValueError):
        return None
    # Docling uses BOTTOMLEFT origin; store axis-aligned box as x0,y0,x1,y1.
    return {
        "x0": left,
        "y0": min(bottom, top),
        "x1": right,
        "y1": max(bottom, top),
    }


def _first_prov(item: dict[str, Any]) -> tuple[int | None, dict[str, float] | None]:
    prov = item.get("prov")
    if not isinstance(prov, list) or not prov:
        return None, None
    first = prov[0]
    if not isinstance(first, dict):
        return None, None
    page = first.get("page_no")
    page_int = int(page) if isinstance(page, int) else None
    region = _bbox_to_region(first.get("bbox") if isinstance(first.get("bbox"), dict) else None)
    return page_int, region


def _table_rows(table: dict[str, Any]) -> list[list[str]]:
    data = table.get("data")
    if not isinstance(data, dict):
        return []
    grid = data.get("grid")
    if isinstance(grid, list) and grid:
        rows: list[list[str]] = []
        for row in grid:
            if not isinstance(row, list):
                continue
            cells: list[str] = []
            for cell in row:
                if isinstance(cell, dict):
                    cells.append(str(cell.get("text", "")).strip())
                else:
                    cells.append(str(cell).strip() if cell is not None else "")
            if any(cells):
                rows.append(cells)
        return rows

    table_cells = data.get("table_cells")
    if isinstance(table_cells, list) and table_cells:
        # Fallback: flatten cell texts when grid is absent.
        row = [str(cell.get("text", "")).strip() for cell in table_cells if isinstance(cell, dict)]
        return [row]
    return []


def blocks_from_docling_dict(document: dict[str, Any]) -> list[Block]:
    """Map a Docling `export_to_dict()` document into extraction blocks."""
    blocks: list[Block] = []

    tables = document.get("tables")
    if isinstance(tables, list):
        for index, table in enumerate(tables):
            if not isinstance(table, dict):
                continue
            rows = _table_rows(table)
            page, region = _first_prov(table)
            blocks.append(
                Block(
                    kind="table",
                    payload={"index": index, "rows": rows, "label": table.get("label")},
                    page=page,
                    region=region,
                )
            )

    texts = document.get("texts")
    if isinstance(texts, list):
        for index, item in enumerate(texts):
            if not isinstance(item, dict):
                continue
            text = item.get("text") or item.get("orig") or ""
            if not str(text).strip():
                continue
            page, region = _first_prov(item)
            blocks.append(
                Block(
                    kind="text",
                    payload={
                        "index": index,
                        "text": str(text),
                        "label": item.get("label"),
                    },
                    page=page,
                    region=region,
                )
            )

    return blocks
