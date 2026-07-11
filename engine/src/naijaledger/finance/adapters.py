"""Source-URL keyed adapters: archived bytes → OCDS release package."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from naijaledger.finance.html_portal import ekiti_html_to_ocds_package
from naijaledger.finance.ocds import OcdsNormalizeError, normalize_ocds_document
from naijaledger.sources.types import SourceFormat

ToPackageFn = Callable[..., dict[str, Any]]

EKITI_URL = "https://ocdsportal.azurewebsites.net/Home/Procurements"


@dataclass(frozen=True, slots=True)
class AdapterSpec:
    adapter_id: str
    method_version: str
    formats: frozenset[SourceFormat]
    to_package: ToPackageFn


def _ocds_json_to_package(data: bytes, *, max_rows: int | None = None) -> dict[str, Any]:
    import json

    raw = json.loads(data.decode("utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("releases"), list):
        package: dict[str, Any] = raw
    elif isinstance(raw, dict) and "ocid" in raw:
        package = {"releases": [raw]}
    else:
        raise OcdsNormalizeError("JSON is neither a release nor a release package")
    # Validate early.
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
        to_package=_ekiti_to_package,
    ),
}

# Generic JSON OCDS: matched by format when URL has no specific adapter.
GENERIC_JSON_ADAPTER = AdapterSpec(
    adapter_id="ocds-json",
    method_version="ocds-json-1",
    formats=frozenset({"json"}),
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
