"""Source-URL keyed adapters: archived bytes → OCDS release package or budget load."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from naijaledger.finance.html_portal import ekiti_html_to_ocds_package
from naijaledger.finance.ocds import OcdsNormalizeError, normalize_ocds_document
from naijaledger.sources.types import SourceFormat

ToPackageFn = Callable[..., dict[str, Any]]
LoadKind = Literal["ocds", "budget"]

EKITI_URL = "https://ocdsportal.azurewebsites.net/Home/Procurements"
BUDGET_OFFICE_URL = (
    "https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents"
)


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    adapter_id: str
    method_version: str
    formats: frozenset[SourceFormat]
    load_kind: LoadKind = "ocds"
    to_package: ToPackageFn | None = None


def _ocds_json_to_package(data: bytes, *, max_rows: int | None = None) -> dict[str, Any]:
    import json

    raw = json.loads(data.decode("utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("releases"), list):
        package: dict[str, Any] = raw
    elif isinstance(raw, dict) and "ocid" in raw:
        package = {"releases": [raw]}
    else:
        raise OcdsNormalizeError("JSON is neither a release nor a release package")
    normalize_ocds_document(package)
    if max_rows is not None:
        package = {**package, "releases": list(package.get("releases") or [])[:max_rows]}
    return package


def _ekiti_to_package(data: bytes, *, max_rows: int | None = None) -> dict[str, Any]:
    return ekiti_html_to_ocds_package(data, max_rows=max_rows)


ADAPTERS_BY_URL: dict[str, AdapterSpec] = {
    EKITI_URL.rstrip("/"): AdapterSpec(
        adapter_id="ekiti-html-table",
        method_version="ekiti-html-table-2",
        formats=frozenset({"html"}),
        load_kind="ocds",
        to_package=_ekiti_to_package,
    ),
    BUDGET_OFFICE_URL.rstrip("/"): AdapterSpec(
        adapter_id="budget-office-appropriation",
        method_version="budget-office-appropriation-1",
        formats=frozenset({"pdf"}),
        load_kind="budget",
        to_package=None,
    ),
}

GENERIC_JSON_ADAPTER = AdapterSpec(
    adapter_id="ocds-json",
    method_version="ocds-json-1",
    formats=frozenset({"json"}),
    load_kind="ocds",
    to_package=_ocds_json_to_package,
)


def normalize_source_url(url: str) -> str:
    return url.rstrip("/")


def adapter_for_source(
    *,
    source_url: str,
    document_format: SourceFormat,
) -> AdapterSpec | None:
    specific = ADAPTERS_BY_URL.get(normalize_source_url(source_url))
    if specific is not None and document_format in specific.formats:
        return specific
    if document_format == "json":
        return GENERIC_JSON_ADAPTER
    return None
