"""Open Contracting Partnership (OCP) Data Registry state bulk helpers (spec 0041)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}

# Real OCP pages use <dt>License:</dt><dd>…</dd> in the publication metadata block.
_LICENCE_DT_DD = re.compile(r"(?is)<dt[^>]*>\s*Licen[cs]e\s*:?\s*</dt>\s*<dd[^>]*>(.*?)</dd>")
# Real OCP pages use <dt>Last retrieved:</dt><dd>Mon D, YYYY</dd>.
_LAST_RETRIEVED_DT_DD = re.compile(
    r"(?is)<dt[^>]*>\s*Last retrieved\s*:?\s*</dt>\s*<dd[^>]*>(.*?)</dd>"
)
_LAST_RETRIEVED_INLINE = re.compile(
    r"Last retrieved:\s*([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_LAST_RETRIEVED_DATE = re.compile(
    r"([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_TAG = re.compile(r"<[^>]+>")
_MD_FIELD = re.compile(r"^(?:[-*]\s+)?\*\*(.+?)\*\*:\s*(.+)$", re.MULTILINE)

ATTRIBUTION = "Open Contracting Partnership Data Registry (https://data.open-contracting.org/)"
SOURCE_KIND = "ocp_registry"
MAX_COMPRESSED_BYTES = 50 * 1024 * 1024
MAX_DECOMPRESSED_BYTES = 200 * 1024 * 1024
PAGE_TIMEOUT_S = 30.0
DOWNLOAD_TIMEOUT_S = 60.0
USER_AGENT = "NaijaLedger/ocp-registry"


@dataclass(frozen=True)
class OcpPublication:
    slug: str
    state_name: str
    publication_id: str
    state_code: str


PUBLICATIONS: tuple[OcpPublication, ...] = (
    OcpPublication("abia", "Abia", "107", "AB"),
    OcpPublication("cross-river", "Cross River", "105", "CR"),
    OcpPublication("ebonyi", "Ebonyi", "86", "EB"),
    OcpPublication("edo", "Edo", "102", "ED"),
    OcpPublication("enugu", "Enugu", "104", "EN"),
    OcpPublication("gombe", "Gombe", "103", "GO"),
    OcpPublication("osun", "Osun", "118", "OS"),
    OcpPublication("oyo", "Oyo", "106", "OY"),
    OcpPublication("plateau", "Plateau", "125", "PL"),
)


def publication_page_url(publication_id: str) -> str:
    return f"https://data.open-contracting.org/en/publication/{publication_id}"


def publication_download_url(publication_id: str) -> str:
    return (
        f"https://data.open-contracting.org/en/publication/{publication_id}"
        f"/download?name=full.jsonl.gz"
    )


def default_licences_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "docs" / "licences"


def licence_record_path(licences_dir: Path, slug: str) -> Path:
    return licences_dir / f"ocp-state-{slug}.md"


@dataclass(frozen=True)
class LicenceRecord:
    publication_url: str
    phrase: str
    date_read: str
    signed_by: str


def parse_licence_record(text: str) -> LicenceRecord | None:
    fields = {
        match.group(1).strip().lower(): match.group(2).strip() for match in _MD_FIELD.finditer(text)
    }
    phrase = fields.get("licence phrase as read")
    pub_url = fields.get("publication url")
    date_read = fields.get("date read")
    signed_by = fields.get("signed by")
    if not phrase or not pub_url or not date_read or not signed_by:
        return None
    return LicenceRecord(
        publication_url=pub_url,
        phrase=phrase,
        date_read=date_read,
        signed_by=signed_by,
    )


def load_licence_record(licences_dir: Path, slug: str) -> LicenceRecord | None:
    path = licence_record_path(licences_dir, slug)
    if not path.is_file():
        return None
    return parse_licence_record(path.read_text(encoding="utf-8"))


def parse_licence_field(html: str) -> str | None:
    """Read the publication metadata licence value from a labelled <dt>/<dd> pair.

    Fail closed if that structure is missing. Does not scan the rest of the page
    for the phrase (footer CC notices must not open the gate).
    """
    match = _LICENCE_DT_DD.search(html)
    if match is None:
        return None
    text = _TAG.sub(" ", match.group(1))
    value = re.sub(r"\s+", " ", text).strip()
    return value or None


def licence_field_is_pddl(field: str) -> bool:
    folded = field.strip().casefold()
    return "public domain dedication" in folded


def licence_matches_record(field: str, record: LicenceRecord) -> bool:
    """PDDL on the page is required; the signed phrase detects drift / mismatch."""
    if not licence_field_is_pddl(field):
        return False
    # Short-form PDDL on the page is enough when the signed record is also PDDL.
    if licence_field_is_pddl(record.phrase):
        return True
    return field.strip().casefold() == record.phrase.strip().casefold()


def _date_from_month_day_year(month_token: str, day: str, year: str) -> date | None:
    month = _MONTHS.get(month_token[:3].lower())
    if month is None:
        return None
    return date(int(year), month, int(day))


def parse_last_retrieved(html: str) -> date | None:
    """Read the publication's Last retrieved date (dt/dd first, then inline text)."""
    dt_dd = _LAST_RETRIEVED_DT_DD.search(html)
    if dt_dd is not None:
        text = _TAG.sub(" ", dt_dd.group(1))
        text = re.sub(r"\s+", " ", text).strip()
        match = _LAST_RETRIEVED_DATE.search(text)
        if match is not None:
            return _date_from_month_day_year(match.group(1), match.group(2), match.group(3))
    match = _LAST_RETRIEVED_INLINE.search(html)
    if match is None:
        return None
    return _date_from_month_day_year(match.group(1), match.group(2), match.group(3))


def flatten_compiled_release(release: dict[str, Any]) -> dict[str, Any]:
    """Unwrap Edo-style compiled wrappers; no-op for normal releases."""
    out = dict(release)
    tender = out.get("tender")
    if isinstance(tender, dict) and isinstance(tender.get("tender"), dict):
        out["tender"] = dict(tender["tender"])

    awards = out.get("awards")
    if isinstance(awards, list):
        flat_awards: list[Any] = []
        for item in awards:
            if not isinstance(item, dict):
                continue
            inner = item.get("awards")
            if isinstance(inner, list) and item.get("suppliers") is None:
                for nested in inner:
                    if isinstance(nested, dict):
                        flat_awards.append(dict(nested))
            else:
                flat_awards.append(item)
        out["awards"] = flat_awards

    singular = out.get("contract")
    if isinstance(singular, dict) and isinstance(singular.get("contracts"), list):
        out["contracts"] = [dict(c) for c in singular["contracts"] if isinstance(c, dict)]
        out.pop("contract", None)

    return out


def copy_contract_suppliers_from_awards(release: dict[str, Any]) -> dict[str, Any]:
    out = dict(release)
    awards = out.get("awards") or []
    by_id: dict[str, dict[str, Any]] = {}
    if isinstance(awards, list):
        for award in awards:
            if isinstance(award, dict) and award.get("id") is not None:
                by_id[str(award["id"])] = award
    contracts = out.get("contracts")
    if not isinstance(contracts, list):
        return out
    patched: list[dict[str, Any]] = []
    for contract in contracts:
        if not isinstance(contract, dict):
            continue
        item = dict(contract)
        suppliers = item.get("suppliers")
        if not suppliers:
            award_ref = item.get("awardID")
            award = by_id.get(str(award_ref)) if award_ref is not None else None
            if award is not None and award.get("suppliers"):
                item["suppliers"] = award["suppliers"]
        patched.append(item)
    out["contracts"] = patched
    return out


def ensure_ocds_ids(release: dict[str, Any]) -> dict[str, Any]:
    """Fill missing award/contract publisher ids before normalize.

    Contract namespacing (``{ocid}:{id}``) is applied in ``normalize_ocds_release``
    so every caller of the shared normalizer gets the same upsert identity.
    """
    out = dict(release)
    ocid = str(out.get("ocid") or "").strip()
    awards = out.get("awards")
    if isinstance(awards, list):
        fixed_awards: list[dict[str, Any]] = []
        for index, award in enumerate(awards):
            if not isinstance(award, dict):
                continue
            item = dict(award)
            if item.get("id") is None or not str(item.get("id")).strip():
                item["id"] = f"{ocid}:award:{index}"
            fixed_awards.append(item)
        out["awards"] = fixed_awards
    contracts = out.get("contracts")
    if isinstance(contracts, list):
        fixed_contracts: list[dict[str, Any]] = []
        for index, contract in enumerate(contracts):
            if not isinstance(contract, dict):
                continue
            item = dict(contract)
            if item.get("id") is None or not str(item.get("id")).strip():
                item["id"] = f"contract:{index}"
            fixed_contracts.append(item)
        out["contracts"] = fixed_contracts
    return out


def prepare_release_dict(release: dict[str, Any]) -> dict[str, Any]:
    flat = flatten_compiled_release(release)
    with_suppliers = copy_contract_suppliers_from_awards(flat)
    return ensure_ocds_ids(with_suppliers)


def normalize_ocp_release(release_dict: dict[str, Any]) -> Any:
    """Normalize OCP release with OCP-specific identity semantics.

    OCP uses:
    - One award row per OCDS award ID (first supplier primary, rest in meta)
    - Contract IDs namespaced as {ocid}:{raw_id}

    This keeps NOCOPO/Ekiti unchanged (they use the standard normalize_ocds_release).
    """
    from naijaledger.finance.ocds import normalize_ocds_release
    from naijaledger.finance.ocds_models import NormalizedAward, NormalizedContract

    normalized = normalize_ocds_release(release_dict)
    ocid = normalized.ocid or ""

    # Collapse multi-supplier awards to one row per OCDS ID
    collapsed_awards = []
    seen_award_ids = set()
    for award in normalized.awards:
        if award.ocds_award_id in seen_award_ids:
            continue
        seen_award_ids.add(award.ocds_award_id)

        # Find all suppliers for this award ID (refs → canonical names for meta).
        supplier_refs = [
            a.supplier_ref for a in normalized.awards if a.ocds_award_id == award.ocds_award_id
        ]

        meta = dict(award.meta or {})
        if len(supplier_refs) > 1:
            names: list[str] = []
            for ref in supplier_refs[1:]:
                party = normalized.parties.get(ref)
                names.append(party.canonical_name if party is not None else ref)
            meta["additional_supplier_names"] = names

        collapsed_awards.append(
            NormalizedAward(
                ocds_award_id=award.ocds_award_id,
                supplier_ref=supplier_refs[0],
                value_amount=award.value_amount,
                currency=award.currency,
                awarded_at=award.awarded_at,
                meta=meta if meta else None,
            )
        )
    normalized.awards = collapsed_awards

    # Namespace contract IDs as {ocid}:{raw_id}
    namespaced_contracts = []
    for index, contract in enumerate(normalized.contracts):
        if contract.ocds_contract_id:
            raw_id = contract.ocds_contract_id
        else:
            raw_id = f"contract:{index}"

        if ocid and not raw_id.startswith(f"{ocid}:"):
            namespaced_id = f"{ocid}:{raw_id}"
        else:
            namespaced_id = raw_id

        meta = dict(contract.meta or {})
        meta["ocds_contract_id_raw"] = raw_id

        namespaced_contracts.append(
            NormalizedContract(
                ocds_contract_id=namespaced_id,
                award_ref=contract.award_ref,
                supplier_ref=contract.supplier_ref,
                agency_ref=contract.agency_ref,
                value_amount=contract.value_amount,
                currency=contract.currency,
                signed_at=contract.signed_at,
                period=contract.period,
                status=contract.status,
                meta=meta,
            )
        )
    normalized.contracts = namespaced_contracts

    return normalized


def stamp_normalized_release(
    release: Any,
    *,
    state_code: str,
    publication_id: str,
    retrieved_on: date,
) -> Any:
    """Stamp OCP meta onto a NormalizedRelease (mutates in place for call-site simplicity)."""
    retrieved = retrieved_on.isoformat()
    if release.tender is not None:
        release.tender.state_code = state_code
        tender_meta = dict(release.tender.meta or {})
        tender_meta.update(
            {
                "ocp_publication_id": publication_id,
                "ocp_retrieved_on": retrieved,
                "source_kind": SOURCE_KIND,
                "attribution": ATTRIBUTION,
            }
        )
        release.tender.meta = tender_meta
    for award in release.awards:
        award_meta = dict(award.meta or {})
        award_meta["source_kind"] = SOURCE_KIND
        award.meta = award_meta
    for contract in release.contracts:
        contract_meta = dict(contract.meta or {})
        contract_meta["source_kind"] = SOURCE_KIND
        # ocds_contract_id_raw is set once in normalize_ocp_release; do not recompute.
        contract.meta = contract_meta
    return release
