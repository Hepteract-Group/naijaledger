from typing import TypedDict

from sqlalchemy.engine import Connection

from naijaledger.seeds.catalog import SEED_APPROVED_BY, SEED_AUTO_APPROVE_ROLES, SEED_CATALOG
from naijaledger.sources.models import SourceCreate, SourceUpdate
from naijaledger.sources.service import (
    approve_source,
    create_source,
    demote_to_proposed,
    get_source_by_url_and_format,
    list_sources,
    retire_source,
    update_source,
)

# Canonical URL fixes for sources already seeded with obsolete endpoints.
_SEED_URL_CORRECTIONS: dict[str, str] = {
    "https://www.budgetoffice.gov.ng/": (
        "https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents"
    ),
    "https://budgetoffice.gov.ng/": (
        "https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents"
    ),
    "https://neiti.gov.ng/": "https://neiti.gov.ng/documents/all",
}

# Federal source audit (specs/0005-state-ocds-portal-audit.md).
_SEED_FEDERAL_SOURCE_CORRECTIONS: dict[str, SourceUpdate] = {
    "https://nocopo.bpp.gov.ng/": SourceUpdate(
        url="https://nocopo.bpp.gov.ng/Open-Data",
        name="Nigeria Open Contracting Portal (NOCOPO) — Open Data",
        fetch_method="playwright",
    ),
}

_RETIRED_FEDERAL_SOURCE_URLS: tuple[str, ...] = (
    "https://opentreasury.gov.ng/",
    "https://payment.gov.ng/",
)

# State OCDS portal audit (specs/0005-state-ocds-portal-audit.md).
_SEED_STATE_PORTAL_CORRECTIONS: dict[str, SourceUpdate] = {
    "https://lagosppaocds.azurewebsites.net/": SourceUpdate(
        url="https://www.lagosppa.gov.ng/registered-awards/",
        name="Lagos State Public Procurement Agency — Registered Awards",
        region="Lagos",
    ),
    "https://lagosstate.gov.ng/lsppa/": SourceUpdate(
        url="https://www.lagosppa.gov.ng/registered-awards/",
        name="Lagos State Public Procurement Agency — Registered Awards",
        region="Lagos",
    ),
    "https://ekitibppaocds.azurewebsites.net/": SourceUpdate(
        url="https://ocdsportal.azurewebsites.net/Home/Procurements",
    ),
    "https://ocdsportal.azurewebsites.net/": SourceUpdate(
        url="https://ocdsportal.azurewebsites.net/Home/Procurements",
    ),
    "https://adamawappaocds.azurewebsites.net/": SourceUpdate(
        url="https://ocdsbpp.adamawastate.gov.ng/projects",
        name="Adamawa State Open Contracting Portal",
    ),
    "https://bpp.adamawastate.gov.ng/": SourceUpdate(
        url="https://ocdsbpp.adamawastate.gov.ng/projects",
        name="Adamawa State Open Contracting Portal",
    ),
    "https://www.ocds.kdsg.gov.ng/": SourceUpdate(
        url="https://www.ocds.kdsg.gov.ng/Projects",
    ),
    "https://ocds.dueprocess.jg.gov.ng/": SourceUpdate(
        url="https://dueprocess.jigawastate.gov.ng/contracts",
        name="Jigawa State Open Contracting Portal",
    ),
    "https://anambrappaocds.azurewebsites.net/": SourceUpdate(
        url="https://eprocure.bpp.an.gov.ng/awarded_contracts.php",
        name="Anambra State Public Procurement Portal",
    ),
    "https://eprocure.bpp.an.gov.ng/": SourceUpdate(
        url="https://eprocure.bpp.an.gov.ng/awarded_contracts.php",
    ),
    "https://eprocure.bpp.an.gov.ng/tenders.php": SourceUpdate(
        url="https://eprocure.bpp.an.gov.ng/awarded_contracts.php",
    ),
    "https://procurement.benuestate.gov.ng/": SourceUpdate(
        url="https://procurement.benuestate.gov.ng/all-awards/",
    ),
    "https://procurement.benuestate.gov.ng/tenders": SourceUpdate(
        url="https://procurement.benuestate.gov.ng/all-awards/",
    ),
    "https://kwppa.kwarastate.gov.ng/ocds-portal/awarded-contracts": SourceUpdate(
        url="https://project.dueprocess.gm.gov.ng/projects",
        name="Gombe State Due Process Portal",
        region="Gombe",
    ),
    "https://kwppa.kwarastate.gov.ng/ocds-portal/": SourceUpdate(
        url="https://project.dueprocess.gm.gov.ng/projects",
        name="Gombe State Due Process Portal",
        region="Gombe",
    ),
}

_RETIRED_STATE_PORTAL_URLS: tuple[str, ...] = (
    "https://ondobppaocds.azurewebsites.net/",
    "https://osunbppaocds.azurewebsites.net/",
    "https://riversbppaocds.azurewebsites.net/",
)

_PLAYWRIGHT_SOURCE_URLS: frozenset[str] = frozenset(
    {
        "https://nocopo.bpp.gov.ng/Open-Data",
        "https://project.dueprocess.gm.gov.ng/projects",
    }
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


def _apply_seed_federal_source_corrections(connection: Connection) -> tuple[int, int]:
    corrected = 0
    retired = 0
    for old_url, update in _SEED_FEDERAL_SOURCE_CORRECTIONS.items():
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

    for old_url in _RETIRED_FEDERAL_SOURCE_URLS:
        for source in list_sources(connection):
            if source.url != old_url:
                continue
            if source.status != "retired":
                retire_source(connection, source.id)
                retired += 1

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


def _apply_seed_playwright_fetch_corrections(connection: Connection) -> int:
    corrected = 0
    for source in list_sources(connection):
        if source.url not in _PLAYWRIGHT_SOURCE_URLS:
            continue
        if source.fetch_method == "playwright":
            continue
        update_source(
            connection,
            source.id,
            SourceUpdate(fetch_method="playwright"),
        )
        corrected += 1
    return corrected


def apply_seed_catalog(
    connection: Connection,
    *,
    entries: list[SourceCreate] | None = None,
    approved_by: str = SEED_APPROVED_BY,
) -> SeedApplySummary:
    catalog = entries if entries is not None else SEED_CATALOG
    corrected, retired = _apply_seed_url_corrections(connection)
    federal_corrected, federal_retired = _apply_seed_federal_source_corrections(connection)
    state_corrected, state_retired = _apply_seed_state_portal_corrections(connection)
    corrected += federal_corrected + state_corrected
    corrected += _apply_seed_playwright_fetch_corrections(connection)
    retired += federal_retired + state_retired
    summary: SeedApplySummary = {
        "created": 0,
        "skipped": 0,
        "approved": 0,
        "corrected": corrected,
        "retired": retired,
    }

    for entry in catalog:
        existing = get_source_by_url_and_format(connection, entry.url, entry.format)
        auto_approve = entry.ingest_role in SEED_AUTO_APPROVE_ROLES
        if existing is not None:
            summary["skipped"] += 1
            if existing.ingest_role != entry.ingest_role:
                update_source(
                    connection,
                    existing.id,
                    SourceUpdate(ingest_role=entry.ingest_role),
                )
                summary["corrected"] += 1
                existing = get_source_by_url_and_format(connection, entry.url, entry.format)
                assert existing is not None
            if auto_approve:
                if existing.status == "proposed":
                    approve_source(connection, existing.id, approved_by=approved_by)
                    summary["approved"] += 1
            elif existing.status == "approved":
                demote_to_proposed(connection, existing.id)
                summary["corrected"] += 1
            continue

        created = create_source(connection, entry)
        summary["created"] += 1
        if auto_approve and created.status == "proposed":
            approve_source(connection, created.id, approved_by=approved_by)
            summary["approved"] += 1

    return summary
