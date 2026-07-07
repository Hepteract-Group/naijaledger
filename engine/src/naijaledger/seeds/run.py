from typing import TypedDict

from sqlalchemy.engine import Connection

from naijaledger.seeds.catalog import SEED_APPROVED_BY, SEED_CATALOG
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import (
    approve_source,
    create_source,
    get_source_by_url_and_format,
)


class SeedApplySummary(TypedDict):
    created: int
    skipped: int
    approved: int


def apply_seed_catalog(
    connection: Connection,
    *,
    entries: list[SourceCreate] | None = None,
    approved_by: str = SEED_APPROVED_BY,
) -> SeedApplySummary:
    catalog = entries if entries is not None else SEED_CATALOG
    summary: SeedApplySummary = {"created": 0, "skipped": 0, "approved": 0}

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
