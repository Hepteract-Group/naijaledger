"""Pure OCDS release → finance DTO mapping (E5.2)."""

from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from naijaledger.finance.ocds_models import (
    NormalizedAward,
    NormalizedContract,
    NormalizedParty,
    NormalizedRelease,
    NormalizedTender,
)
from naijaledger.finance.types import PartyType, TenderMethod

_METHOD_MAP: dict[str, TenderMethod] = {
    "open": "open",
    "selective": "selective",
    "limited": "limited",
    "direct": "direct",
}

_AGENCY_ROLES = frozenset({"buyer", "procuringentity"})
_SUPPLIER_ROLES = frozenset({"supplier", "tenderer"})


class OcdsNormalizeError(ValueError):
    pass


def unwrap_extraction_payload(payload: dict[str, Any]) -> Any:
    if "value" in payload and len(payload) <= 2:
        return payload["value"]
    return payload


def amount_to_kobo(amount: Any) -> int | None:
    if amount is None:
        return None
    try:
        major = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        return None
    return int((major * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def map_procurement_method(raw: str | None) -> TenderMethod | None:
    if raw is None:
        return None
    return _METHOD_MAP.get(raw.strip().lower())


def _parse_datetime(raw: Any) -> datetime | None:
    if raw is None or not isinstance(raw, str) or not raw.strip():
        return None
    text = raw.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _roles(party: dict[str, Any]) -> set[str]:
    roles = party.get("roles") or []
    if not isinstance(roles, list):
        return set()
    return {str(role).strip().lower() for role in roles if role}


def _party_type_for(roles: set[str]) -> PartyType:
    if roles & _AGENCY_ROLES:
        return "agency"
    if roles & _SUPPLIER_ROLES:
        return "company"
    return "company"


def _party_ref(party: dict[str, Any], index: int) -> str:
    party_id = party.get("id")
    if isinstance(party_id, str) and party_id.strip():
        return party_id.strip()
    name = party.get("name")
    if isinstance(name, str) and name.strip():
        return f"name:{name.strip().lower()}"
    return f"party:{index}"


def _identifiers_from_party(party: dict[str, Any]) -> dict[str, Any]:
    identifiers: dict[str, Any] = {}
    if party.get("id") is not None:
        identifiers["ocds_id"] = party["id"]
    identifier = party.get("identifier")
    if isinstance(identifier, dict):
        identifiers["identifier"] = identifier
    additional = party.get("additionalIdentifiers")
    if isinstance(additional, list) and additional:
        identifiers["additionalIdentifiers"] = additional
    return identifiers


def _money_fields(value: Any) -> tuple[int | None, str]:
    if not isinstance(value, dict):
        return None, "NGN"
    currency = value.get("currency")
    if not isinstance(currency, str) or not currency.strip():
        currency = "NGN"
    return amount_to_kobo(value.get("amount")), currency.strip().upper()


def _normalize_parties(release: dict[str, Any]) -> dict[str, NormalizedParty]:
    parties_out: dict[str, NormalizedParty] = {}
    raw_parties = release.get("parties") or []
    if not isinstance(raw_parties, list):
        return parties_out
    for index, party in enumerate(raw_parties):
        if not isinstance(party, dict):
            continue
        name = party.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        ref = _party_ref(party, index)
        roles = _roles(party)
        address = party.get("address") if isinstance(party.get("address"), dict) else None
        parties_out[ref] = NormalizedParty(
            party_type=_party_type_for(roles),
            canonical_name=name.strip(),
            identifiers=_identifiers_from_party(party),
            address=address,
            meta={"roles": sorted(roles)} if roles else None,
        )
    return parties_out


def _find_agency_ref(parties: dict[str, NormalizedParty], release: dict[str, Any]) -> str | None:
    for ref, party in parties.items():
        roles = set((party.meta or {}).get("roles") or [])
        if roles & _AGENCY_ROLES:
            return ref
    buyer = release.get("buyer")
    if isinstance(buyer, dict):
        buyer_id = buyer.get("id")
        if isinstance(buyer_id, str) and buyer_id in parties:
            return buyer_id
        name = buyer.get("name")
        if isinstance(name, str):
            key = f"name:{name.strip().lower()}"
            if key in parties:
                return key
    return None


def _ensure_party_from_org(
    parties: dict[str, NormalizedParty],
    org: dict[str, Any] | None,
    *,
    party_type: PartyType,
    fallback_ref: str,
) -> str | None:
    if not isinstance(org, dict):
        return None
    org_id = org.get("id")
    if isinstance(org_id, str) and org_id in parties:
        return org_id
    name = org.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    ref = org_id.strip() if isinstance(org_id, str) and org_id.strip() else fallback_ref
    if ref not in parties:
        parties[ref] = NormalizedParty(
            party_type=party_type,
            canonical_name=name.strip(),
            identifiers={"ocds_id": org_id} if org_id is not None else {},
        )
    return ref


def _normalize_tender(
    release: dict[str, Any],
    parties: dict[str, NormalizedParty],
    ocid: str,
    skipped: list[str],
) -> NormalizedTender | None:
    tender = release.get("tender")
    if not isinstance(tender, dict):
        skipped.append("no tender object")
        return None
    title = tender.get("title")
    if not isinstance(title, str) or not title.strip():
        skipped.append("tender missing title")
        return None
    agency_ref = _find_agency_ref(parties, release)
    if agency_ref is None:
        procuring = tender.get("procuringEntity")
        agency_ref = _ensure_party_from_org(
            parties,
            procuring if isinstance(procuring, dict) else None,
            party_type="agency",
            fallback_ref="agency:procuringEntity",
        )
    if agency_ref is None:
        skipped.append("no agency/buyer resolvable for tender")
        return None

    raw_method = tender.get("procurementMethod")
    method = map_procurement_method(raw_method if isinstance(raw_method, str) else None)
    value_amount, currency = _money_fields(tender.get("value"))
    tender_period = tender.get("tenderPeriod")
    opens_at = closes_at = None
    if isinstance(tender_period, dict):
        opens_at = _parse_datetime(tender_period.get("startDate"))
        closes_at = _parse_datetime(tender_period.get("endDate"))

    meta: dict[str, Any] = {}
    if isinstance(raw_method, str) and method is None:
        meta["procurementMethod"] = raw_method
    raw_tenderers = tender.get("numberOfTenderers")
    if isinstance(raw_tenderers, bool):
        pass
    elif isinstance(raw_tenderers, int) and raw_tenderers >= 0:
        meta["numberOfTenderers"] = raw_tenderers
    elif isinstance(raw_tenderers, float) and raw_tenderers >= 0 and raw_tenderers.is_integer():
        meta["numberOfTenderers"] = int(raw_tenderers)

    return NormalizedTender(
        ocid=ocid,
        agency_ref=agency_ref,
        title=title.strip(),
        method=method,
        value_amount=value_amount,
        currency=currency,
        bidding_opens_at=opens_at,
        bidding_closes_at=closes_at,
        meta=meta or None,
    )


def _supplier_refs_from_award(
    award: dict[str, Any],
    parties: dict[str, NormalizedParty],
) -> list[str]:
    refs: list[str] = []
    suppliers = award.get("suppliers") or []
    if not isinstance(suppliers, list):
        return refs
    for index, supplier in enumerate(suppliers):
        if not isinstance(supplier, dict):
            continue
        ref = _ensure_party_from_org(
            parties,
            supplier,
            party_type="company",
            fallback_ref=f"supplier:{award.get('id', index)}:{index}",
        )
        if ref is not None:
            refs.append(ref)
    return refs


def _normalize_awards(
    release: dict[str, Any],
    parties: dict[str, NormalizedParty],
    skipped: list[str],
) -> list[NormalizedAward]:
    awards_out: list[NormalizedAward] = []
    raw_awards = release.get("awards") or []
    if not isinstance(raw_awards, list):
        return awards_out
    for award in raw_awards:
        if not isinstance(award, dict):
            continue
        ocds_award_id = award.get("id")
        award_id = str(ocds_award_id) if ocds_award_id is not None else None
        supplier_refs = _supplier_refs_from_award(award, parties)
        if not supplier_refs:
            skipped.append(f"award {award_id or '?'} has no suppliers")
            continue
        value_amount, currency = _money_fields(award.get("value"))
        awarded_at = _parse_datetime(award.get("date"))
        for supplier_ref in supplier_refs:
            awards_out.append(
                NormalizedAward(
                    ocds_award_id=award_id,
                    supplier_ref=supplier_ref,
                    value_amount=value_amount,
                    currency=currency,
                    awarded_at=awarded_at,
                )
            )
    return awards_out


def _normalize_contracts(
    release: dict[str, Any],
    parties: dict[str, NormalizedParty],
    agency_ref: str | None,
    skipped: list[str],
) -> list[NormalizedContract]:
    contracts_out: list[NormalizedContract] = []
    raw_contracts = release.get("contracts") or []
    if not isinstance(raw_contracts, list):
        return contracts_out
    for contract in raw_contracts:
        if not isinstance(contract, dict):
            continue
        ocds_id = contract.get("id")
        contract_id = str(ocds_id) if ocds_id is not None else None
        award_ref = contract.get("awardID")
        award_ref_s = str(award_ref) if award_ref is not None else None

        suppliers = contract.get("suppliers") or []
        supplier_ref = None
        if isinstance(suppliers, list) and suppliers and isinstance(suppliers[0], dict):
            supplier_ref = _ensure_party_from_org(
                parties,
                suppliers[0],
                party_type="company",
                fallback_ref=f"contract-supplier:{contract_id or 'x'}",
            )
        if supplier_ref is None:
            skipped.append(f"contract {contract_id or '?'} has no supplier")
            continue
        if agency_ref is None:
            skipped.append(f"contract {contract_id or '?'} has no agency")
            continue

        value_amount, currency = _money_fields(contract.get("value"))
        signed_at = _parse_datetime(contract.get("dateSigned")) or _parse_datetime(
            contract.get("date")
        )
        period = contract.get("period") if isinstance(contract.get("period"), dict) else None
        status = contract.get("status")
        status_s = str(status) if status is not None else None

        contracts_out.append(
            NormalizedContract(
                ocds_contract_id=contract_id,
                award_ref=award_ref_s,
                supplier_ref=supplier_ref,
                agency_ref=agency_ref,
                value_amount=value_amount,
                currency=currency,
                signed_at=signed_at,
                period=period,
                status=status_s,
            )
        )
    return contracts_out


def normalize_ocds_release(release: dict[str, Any]) -> NormalizedRelease:
    ocid_raw = release.get("ocid")
    if not isinstance(ocid_raw, str) or not ocid_raw.strip():
        raise OcdsNormalizeError("release missing ocid")
    ocid = ocid_raw.strip()
    skipped: list[str] = []
    parties = _normalize_parties(release)
    tender = _normalize_tender(release, parties, ocid, skipped)
    agency_ref = tender.agency_ref if tender is not None else _find_agency_ref(parties, release)
    awards = _normalize_awards(release, parties, skipped)
    contracts = _normalize_contracts(release, parties, agency_ref, skipped)
    return NormalizedRelease(
        ocid=ocid,
        parties=parties,
        tender=tender,
        awards=awards,
        contracts=contracts,
        skipped=skipped,
    )


def normalize_ocds_document(doc: Any) -> list[NormalizedRelease]:
    if not isinstance(doc, dict):
        raise OcdsNormalizeError("OCDS document must be an object")
    if isinstance(doc.get("releases"), list):
        releases: list[NormalizedRelease] = []
        for index, item in enumerate(doc["releases"]):
            if not isinstance(item, dict):
                raise OcdsNormalizeError(f"releases[{index}] is not an object")
            releases.append(normalize_ocds_release(item))
        return releases
    if "ocid" in doc:
        return [normalize_ocds_release(doc)]
    raise OcdsNormalizeError("document is neither a release nor a release package")
