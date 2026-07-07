from typing import TypedDict

from sqlalchemy.engine import Connection

from naijaledger.seeds.catalog import SEED_APPROVED_BY, SEED_CATALOG
from naijaledger.sources.models import SourceCreate, SourceUpdate
from naijaledger.sources.service import (
    approve_source,
    create_source,
    get_source_by_url_and_format,
    list_sources,
    retire_source,
    update_source,
)

# Canonical URL fixes for sources already seeded with obsolete endpoints.
_SEED_URL_CORRECTIONS: dict[str, str] = {
    "https://payment.gov.ng/": "https://opentreasury.gov.ng/",
    "https://www.budgetoffice.gov.ng/": "https://budgetoffice.gov.ng/",
}

# State OCDS portal audit (specs/0005-state-ocds-portal-audit.md).
_SEED_STATE_PORTAL_CORRECTIONS: dict[str, SourceUpdate] = {
    "https://lagosppaocds.azurewebsites.net/": SourceUpdate(
        url="https://lagosstate.gov.ng/lsppa/",
        name="Lagos State Public Procurement Agency (LSPPA)",
        region="Lagos",
    ),
    "https://ekitibppaocds.azurewebsites.net/": SourceUpdate(
        url="https://ocdsportal.azurewebsites.net/",
    ),
    "https://adamawappaocds.azurewebsites.net/": SourceUpdate(
        url="https://bpp.adamawastate.gov.ng/",
        name="Adamawa State Bureau of Public Procurement",
    ),
    "https://anambrappaocds.azurewebsites.net/": SourceUpdate(
        url="https://eprocure.bpp.an.gov.ng/",
        name="Anambra State Public Procurement Portal",
    ),
}

_RETIRED_STATE_PORTAL_URLS: tuple[str, ...] = (
    "https://ondobppaocds.azurewebsites.net/",
    "https://osunbppaocds.azurewebsites.net/",
    "https://riversbppaocds.azurewebsites.net/",
)


class SeedApplySummary(TypedDict):
    created: int
    skipped: int
    approved: int
    corrected: int
    retired: int


def _apply_seed_url_corrections(connection: Connection) -> tuple[int, int]:
    corrected = 0
    retired = 0
    for old_url, new_url in _SEED_URL_CORRECTIONS.items():
        for source in list_sources(connection):
            if source.url != old_url:
                continue
            replacement = get_source_by_url_and_format(connection, new_url, source.format)
            if replacement is not None and replacement.id != source.id:
                if source.status != "retired":
                    retire_source(connection, source.id)
                    retired += 1
                continue
            update_source(
                connection,
                source.id,
                SourceUpdate(url=new_url),
            )
            corrected += 1
    return corrected, retired


def _apply_seed_state_portal_corrections(connection: Connection) -> tuple[int, int]:
    corrected = 0
    retired = 0
    for old_url, update in _SEED_STATE_PORTAL_CORRECTIONS.items():
        for source in list_sources(connection):
            if source.url != old_url:
                continue
            new_url = update.url
            if new_url is None:
                continue
            replacement = get_source_by_url_and_format(connection, new_url, source.format)
            if replacement is not None and replacement.id != source.id:
                if source.status != "retired":
                    retire_source(connection, source.id)
                    retired += 1
                continue
            update_source(connection, source.id, update)
            corrected += 1

    for old_url in _RETIRED_STATE_PORTAL_URLS:
        for source in list_sources(connection):
            if source.url != old_url:
                continue
            if source.status != "retired":
                retire_source(connection, source.id)
                retired += 1

    return corrected, retired


def apply_seed_catalog(
    connection: Connection,
    *,
    entries: list[SourceCreate] | None = None,
    approved_by: str = SEED_APPROVED_BY,
) -> SeedApplySummary:
    catalog = entries if entries is not None else SEED_CATALOG
    corrected, retired = _apply_seed_url_corrections(connection)
    state_corrected, state_retired = _apply_seed_state_portal_corrections(connection)
    corrected += state_corrected
    retired += state_retired
    summary: SeedApplySummary = {
        "created": 0,
        "skipped": 0,
        "approved": 0,
        "corrected": corrected,
        "retired": retired,
    }

    for entry in catalog:
        existing = get_source_by_url_and_format(connection, entry.url, entry.format)
        if existing is not None:
            summary["skipped"] += 1
            if existing.status == "proposed":
                approve_source(connection, existing.id, approved_by=approved_by)
                summary["approved"] += 1
            continue

        created = create_source(connection, entry)
        summary["created"] += 1
        if created.status == "proposed":
            approve_source(connection, created.id, approved_by=approved_by)
            summary["approved"] += 1

    return summary
