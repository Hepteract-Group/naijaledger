"""Approved initial source catalog for registry seeding (E2.3).

State OCDS URLs audited 2026-07-07 — see specs/0005-state-ocds-portal-audit.md.
Three slots (Ondo, Osun, Rivers) use substitute states whose portals are live.
"""

from datetime import timedelta

from naijaledger.sources.models import SourceCreate

SEED_ADDED_BY = "seed:e2.3"
SEED_APPROVED_BY = "human:decision-brief-2026-07-07"

_FEDERAL_SOURCES: list[SourceCreate] = [
    SourceCreate(
        name="Nigeria Open Contracting Portal (NOCOPO)",
        jurisdiction="federal",
        category="procurement",
        url="https://nocopo.bpp.gov.ng/",
        fetch_method="http",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Open Treasury Portal",
        jurisdiction="federal",
        category="payments",
        url="https://opentreasury.gov.ng/",
        fetch_method="http",
        format="html",
        expected_cadence=timedelta(days=1),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Budget Office of the Federation",
        jurisdiction="federal",
        category="budget",
        url="https://budgetoffice.gov.ng/",
        fetch_method="http",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="NEITI",
        jurisdiction="federal",
        category="other",
        url="https://neiti.gov.ng/",
        fetch_method="http",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
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
    ),
]

_STATE_PROCUREMENT_SOURCES: list[SourceCreate] = [
    SourceCreate(
        name="Lagos State Public Procurement Agency (LSPPA)",
        jurisdiction="state",
        region="Lagos",
        category="procurement",
        url="https://lagosstate.gov.ng/lsppa/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Kaduna State Open Contracting Portal",
        jurisdiction="state",
        region="Kaduna",
        category="procurement",
        url="https://www.ocds.kdsg.gov.ng/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Ekiti State Open Contracting Portal",
        jurisdiction="state",
        region="Ekiti",
        category="procurement",
        url="https://ocdsportal.azurewebsites.net/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Adamawa State Bureau of Public Procurement",
        jurisdiction="state",
        region="Adamawa",
        category="procurement",
        url="https://bpp.adamawastate.gov.ng/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Kwara State Open Contracting Portal",
        jurisdiction="state",
        region="Kwara",
        category="procurement",
        url="https://kwppa.kwarastate.gov.ng/ocds-portal/awarded-contracts",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Jigawa State Open Contracting Portal",
        jurisdiction="state",
        region="Jigawa",
        category="procurement",
        url="https://ocds.dueprocess.jg.gov.ng/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Anambra State Public Procurement Portal",
        jurisdiction="state",
        region="Anambra",
        category="procurement",
        url="https://eprocure.bpp.an.gov.ng/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
    SourceCreate(
        name="Benue State Procurement Portal",
        jurisdiction="state",
        region="Benue",
        category="procurement",
        url="https://procurement.benuestate.gov.ng/",
        fetch_method="scrapling",
        format="html",
        expected_cadence=timedelta(days=7),
        added_by=SEED_ADDED_BY,
    ),
]

SEED_CATALOG: list[SourceCreate] = _FEDERAL_SOURCES + _STATE_PROCUREMENT_SOURCES
