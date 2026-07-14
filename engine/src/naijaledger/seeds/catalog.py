"""Approved initial source catalog for registry seeding (E2.3).

Content-sampled 2026-07-08 — see specs/0005-state-ocds-portal-audit.md.
Roles: specs/0039-federal-discovery-rescope.md (`ingest_role`).
Fetch today archives *only* this URL (no link-following yet). Leaf pages must contain
award/tender/contract rows; catalog pages (Lagos/Jigawa PDF indexes) need E3.4 discovery.
"""

from datetime import timedelta

from naijaledger.sources.models import SourceCreate
from naijaledger.sources.types import IngestRole

SEED_ADDED_BY = "seed:e2.3"
SEED_APPROVED_BY = "human:decision-brief-2026-07-07"

# Roles that may enter the approved fetch schedule (spec 0039).
SEED_AUTO_APPROVE_ROLES: frozenset[IngestRole] = frozenset({"leaf", "catalog"})

_FEDERAL_SOURCES: list[SourceCreate] = [
    SourceCreate(
        name="Nigeria Open Contracting Portal (NOCOPO) — Open Data",
        jurisdiction="federal",
        category="procurement",
        url="https://nocopo.bpp.gov.ng/Open-Data",
        fetch_method="playwright",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="leaf",
    ),
    SourceCreate(
        name="Budget Office of the Federation — Budget Documents",
        jurisdiction="federal",
        category="budget",
        url="https://budgetoffice.gov.ng/index.php/resources/internal-resources/budget-documents",
        fetch_method="http",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="catalog",
    ),
    SourceCreate(
        name="NEITI — Documents library",
        jurisdiction="federal",
        category="other",
        url="https://neiti.gov.ng/documents/all",
        fetch_method="http",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="catalog",
    ),
    SourceCreate(
        name="OpenStates.ng",
        jurisdiction="federal",
        category="other",
        url="https://openstates.ng/",
        fetch_method="http",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="discovery_ui",
    ),
    SourceCreate(
        name="CAC Beneficial Ownership Register",
        jurisdiction="federal",
        category="company",
        url="https://bor.cac.gov.ng/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=30),
        added_by=SEED_ADDED_BY,
        ingest_role="search_ui",
    ),
]

_STATE_PROCUREMENT_SOURCES: list[SourceCreate] = [
    SourceCreate(
        name="Lagos State Public Procurement Agency — Registered Awards",
        jurisdiction="state",
        region="Lagos",
        category="procurement",
        url="https://www.lagosppa.gov.ng/registered-awards/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="catalog",
    ),
    SourceCreate(
        name="Kaduna State Open Contracting Portal",
        jurisdiction="state",
        region="Kaduna",
        category="procurement",
        url="https://www.ocds.kdsg.gov.ng/Projects",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="leaf",
    ),
    SourceCreate(
        name="Ekiti State Open Contracting Portal",
        jurisdiction="state",
        region="Ekiti",
        category="procurement",
        url="https://ocdsportal.azurewebsites.net/Home/Procurements",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="leaf",
    ),
    SourceCreate(
        name="Adamawa State Open Contracting Portal",
        jurisdiction="state",
        region="Adamawa",
        category="procurement",
        url="https://ocdsbpp.adamawastate.gov.ng/projects",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="leaf",
    ),
    SourceCreate(
        name="Gombe State Due Process Portal",
        jurisdiction="state",
        region="Gombe",
        category="procurement",
        url="https://project.dueprocess.gm.gov.ng/projects",
        fetch_method="playwright",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="leaf",
    ),
    SourceCreate(
        name="Jigawa State Open Contracting Portal",
        jurisdiction="state",
        region="Jigawa",
        category="procurement",
        url="https://dueprocess.jigawastate.gov.ng/contracts",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="catalog",
    ),
    SourceCreate(
        name="Anambra State Public Procurement Portal",
        jurisdiction="state",
        region="Anambra",
        category="procurement",
        url="https://eprocure.bpp.an.gov.ng/awarded_contracts.php",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="leaf",
    ),
    SourceCreate(
        name="Benue State Procurement Portal",
        jurisdiction="state",
        region="Benue",
        category="procurement",
        url="https://procurement.benuestate.gov.ng/all-awards/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
        ingest_role="leaf",
    ),
]

SEED_CATALOG: list[SourceCreate] = _FEDERAL_SOURCES + _STATE_PROCUREMENT_SOURCES
