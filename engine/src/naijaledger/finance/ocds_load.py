"""Thin OCDS load into canonical finance tables (E5.2 / E5.3)."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import String, bindparam, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.engine import Connection

from naijaledger.extractions.models import ProvenanceEdgeCreate
from naijaledger.extractions.service import create_provenance_edge, find_provenance_edge
from naijaledger.finance.ocds_models import (
    LoadResult,
    NormalizedParty,
    NormalizedRelease,
    ProvenanceContext,
)


def _merge_identifiers(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing or {})
    merged.update(incoming)
    return merged


def _link_subject(
    connection: Connection,
    provenance: ProvenanceContext,
    *,
    subject_type: str,
    subject_id: UUID,
    edge_ids: list[UUID],
) -> None:
    existing = find_provenance_edge(
        connection,
        extraction_id=provenance.extraction_id,
        subject_type=subject_type,
        subject_id=subject_id,
    )
    if existing is not None:
        edge_ids.append(existing.id)
        return
    edge = create_provenance_edge(
        connection,
        ProvenanceEdgeCreate(
            document_id=provenance.document_id,
            extraction_id=provenance.extraction_id,
            method=provenance.method,
            derivation=provenance.derivation,
            confidence=provenance.confidence,
            page=provenance.page,
            region=provenance.region,
            subject_type=subject_type,
            subject_id=subject_id,
        ),
    )
    edge_ids.append(edge.id)


def _upsert_party(connection: Connection, party: NormalizedParty) -> UUID:
    existing = connection.execute(
        text(
            """
            SELECT id, aliases, identifiers
            FROM parties
            WHERE party_type = :party_type
              AND lower(canonical_name) = lower(:canonical_name)
            """
        ),
        {"party_type": party.party_type, "canonical_name": party.canonical_name},
    ).first()
    if existing is not None:
        aliases = list(dict.fromkeys([*(existing.aliases or []), *party.aliases]))
        identifiers = _merge_identifiers(existing.identifiers, party.identifiers)
        connection.execute(
            text(
                """
                UPDATE parties
                SET aliases = :aliases,
                    identifiers = CAST(:identifiers AS jsonb),
                    address = COALESCE(CAST(:address AS jsonb), address),
                    meta = COALESCE(CAST(:meta AS jsonb), meta),
                    updated_at = now()
                WHERE id = :id
                """
            ).bindparams(bindparam("aliases", type_=ARRAY(String()))),
            {
                "id": existing.id,
                "aliases": aliases,
                "identifiers": json.dumps(identifiers),
                "address": json.dumps(party.address) if party.address is not None else None,
                "meta": json.dumps(party.meta) if party.meta is not None else None,
            },
        )
        return existing.id  # type: ignore[no-any-return]

    row = connection.execute(
        text(
            """
            INSERT INTO parties (
                party_type, canonical_name, aliases, identifiers, address, meta
            ) VALUES (
                :party_type, :canonical_name, :aliases,
                CAST(:identifiers AS jsonb), CAST(:address AS jsonb), CAST(:meta AS jsonb)
            )
            RETURNING id
            """
        ).bindparams(bindparam("aliases", type_=ARRAY(String()))),
        {
            "party_type": party.party_type,
            "canonical_name": party.canonical_name,
            "aliases": party.aliases,
            "identifiers": json.dumps(party.identifiers),
            "address": json.dumps(party.address) if party.address is not None else None,
            "meta": json.dumps(party.meta) if party.meta is not None else None,
        },
    ).one()
    return row.id  # type: ignore[no-any-return]


def _upsert_tender(
    connection: Connection,
    *,
    ocid: str,
    agency_id: UUID,
    title: str,
    method: str | None,
    value_amount: int | None,
    currency: str,
    bidding_opens_at: Any,
    bidding_closes_at: Any,
    state_code: str | None,
    lga: str | None,
    fiscal_year: int | None,
    meta: dict[str, Any] | None,
) -> UUID:
    existing = connection.execute(
        text("SELECT id FROM tenders WHERE ocid = :ocid"),
        {"ocid": ocid},
    ).first()
    if existing is not None:
        connection.execute(
            text(
                """
                UPDATE tenders
                SET agency_id = :agency_id,
                    title = :title,
                    method = :method,
                    value_amount = :value_amount,
                    currency = :currency,
                    bidding_opens_at = :bidding_opens_at,
                    bidding_closes_at = :bidding_closes_at,
                    state_code = :state_code,
                    lga = :lga,
                    fiscal_year = :fiscal_year,
                    meta = CAST(:meta AS jsonb),
                    updated_at = now()
                WHERE id = :id
                """
            ),
            {
                "id": existing.id,
                "agency_id": agency_id,
                "title": title,
                "method": method,
                "value_amount": value_amount,
                "currency": currency,
                "bidding_opens_at": bidding_opens_at,
                "bidding_closes_at": bidding_closes_at,
                "state_code": state_code,
                "lga": lga,
                "fiscal_year": fiscal_year,
                "meta": json.dumps(meta) if meta is not None else None,
            },
        )
        return existing.id  # type: ignore[no-any-return]

    row = connection.execute(
        text(
            """
            INSERT INTO tenders (
                ocid, agency_id, title, method, value_amount, currency,
                bidding_opens_at, bidding_closes_at, state_code, lga, fiscal_year, meta
            ) VALUES (
                :ocid, :agency_id, :title, :method, :value_amount, :currency,
                :bidding_opens_at, :bidding_closes_at, :state_code, :lga, :fiscal_year,
                CAST(:meta AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "ocid": ocid,
            "agency_id": agency_id,
            "title": title,
            "method": method,
            "value_amount": value_amount,
            "currency": currency,
            "bidding_opens_at": bidding_opens_at,
            "bidding_closes_at": bidding_closes_at,
            "state_code": state_code,
            "lga": lga,
            "fiscal_year": fiscal_year,
            "meta": json.dumps(meta) if meta is not None else None,
        },
    ).one()
    return row.id  # type: ignore[no-any-return]


def _upsert_award(
    connection: Connection,
    *,
    tender_id: UUID,
    supplier_id: UUID,
    ocds_award_id: str | None,
    value_amount: int | None,
    currency: str,
    awarded_at: Any,
    meta: dict[str, Any],
) -> tuple[UUID, bool]:
    if ocds_award_id is not None:
        existing = connection.execute(
            text(
                """
                SELECT id FROM awards
                WHERE tender_id = :tender_id
                  AND supplier_id = :supplier_id
                  AND meta->>'ocds_award_id' = :ocds_award_id
                """
            ),
            {
                "tender_id": tender_id,
                "supplier_id": supplier_id,
                "ocds_award_id": ocds_award_id,
            },
        ).first()
        if existing is not None:
            connection.execute(
                text(
                    """
                    UPDATE awards
                    SET value_amount = :value_amount,
                        currency = :currency,
                        awarded_at = :awarded_at,
                        meta = CAST(:meta AS jsonb),
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {
                    "id": existing.id,
                    "value_amount": value_amount,
                    "currency": currency,
                    "awarded_at": awarded_at,
                    "meta": json.dumps(meta),
                },
            )
            return existing.id, False

    row = connection.execute(
        text(
            """
            INSERT INTO awards (
                tender_id, supplier_id, value_amount, currency, awarded_at, meta
            ) VALUES (
                :tender_id, :supplier_id, :value_amount, :currency, :awarded_at,
                CAST(:meta AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "tender_id": tender_id,
            "supplier_id": supplier_id,
            "value_amount": value_amount,
            "currency": currency,
            "awarded_at": awarded_at,
            "meta": json.dumps(meta),
        },
    ).one()
    return row.id, True


def _upsert_contract(
    connection: Connection,
    *,
    award_id: UUID | None,
    supplier_id: UUID,
    agency_id: UUID,
    ocds_contract_id: str | None,
    value_amount: int | None,
    currency: str,
    signed_at: Any,
    period: dict[str, Any] | None,
    status: str | None,
    meta: dict[str, Any],
) -> tuple[UUID, bool]:
    if ocds_contract_id is not None:
        existing = connection.execute(
            text(
                """
                SELECT id FROM contracts
                WHERE agency_id = :agency_id
                  AND supplier_id = :supplier_id
                  AND meta->>'ocds_contract_id' = :ocds_contract_id
                """
            ),
            {
                "agency_id": agency_id,
                "supplier_id": supplier_id,
                "ocds_contract_id": ocds_contract_id,
            },
        ).first()
        if existing is not None:
            connection.execute(
                text(
                    """
                    UPDATE contracts
                    SET award_id = :award_id,
                        value_amount = :value_amount,
                        currency = :currency,
                        signed_at = :signed_at,
                        period = CAST(:period AS jsonb),
                        status = :status,
                        meta = CAST(:meta AS jsonb),
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {
                    "id": existing.id,
                    "award_id": award_id,
                    "value_amount": value_amount,
                    "currency": currency,
                    "signed_at": signed_at,
                    "period": json.dumps(period) if period is not None else None,
                    "status": status,
                    "meta": json.dumps(meta),
                },
            )
            return existing.id, False

    row = connection.execute(
        text(
            """
            INSERT INTO contracts (
                award_id, supplier_id, agency_id, value_amount, currency,
                signed_at, period, status, meta
            ) VALUES (
                :award_id, :supplier_id, :agency_id, :value_amount, :currency,
                :signed_at, CAST(:period AS jsonb), :status, CAST(:meta AS jsonb)
            )
            RETURNING id
            """
        ),
        {
            "award_id": award_id,
            "supplier_id": supplier_id,
            "agency_id": agency_id,
            "value_amount": value_amount,
            "currency": currency,
            "signed_at": signed_at,
            "period": json.dumps(period) if period is not None else None,
            "status": status,
            "meta": json.dumps(meta),
        },
    ).one()
    return row.id, True


def load_normalized_release(
    connection: Connection,
    release: NormalizedRelease,
    *,
    provenance: ProvenanceContext | None = None,
) -> LoadResult:
    party_ids: dict[str, UUID] = {}
    edge_ids: list[UUID] = []
    for ref, party in release.parties.items():
        party_ids[ref] = _upsert_party(connection, party)

    result = LoadResult(
        party_ids=party_ids,
        parties_upserted=len(party_ids),
    )

    if provenance is not None:
        for party_id in party_ids.values():
            _link_subject(
                connection,
                provenance,
                subject_type="party",
                subject_id=party_id,
                edge_ids=edge_ids,
            )

    tender_id: UUID | None = None
    if release.tender is not None:
        agency_id = party_ids[release.tender.agency_ref]
        tender_id = _upsert_tender(
            connection,
            ocid=release.tender.ocid,
            agency_id=agency_id,
            title=release.tender.title,
            method=release.tender.method,
            value_amount=release.tender.value_amount,
            currency=release.tender.currency,
            bidding_opens_at=release.tender.bidding_opens_at,
            bidding_closes_at=release.tender.bidding_closes_at,
            state_code=release.tender.state_code,
            lga=release.tender.lga,
            fiscal_year=release.tender.fiscal_year,
            meta=release.tender.meta,
        )
        result.tender_id = tender_id
        result.tenders_upserted = 1
        if provenance is not None:
            _link_subject(
                connection,
                provenance,
                subject_type="tender",
                subject_id=tender_id,
                edge_ids=edge_ids,
            )

    award_id_by_ocds: dict[str, UUID] = {}
    if tender_id is not None:
        for award in release.awards:
            meta = {"ocds_award_id": award.ocds_award_id, **(award.meta or {})}
            award_id, inserted = _upsert_award(
                connection,
                tender_id=tender_id,
                supplier_id=party_ids[award.supplier_ref],
                ocds_award_id=award.ocds_award_id,
                value_amount=award.value_amount,
                currency=award.currency,
                awarded_at=award.awarded_at,
                meta=meta,
            )
            result.award_ids.append(award_id)
            if inserted:
                result.awards_inserted += 1
            if award.ocds_award_id is not None:
                award_id_by_ocds[award.ocds_award_id] = award_id
            if provenance is not None:
                _link_subject(
                    connection,
                    provenance,
                    subject_type="award",
                    subject_id=award_id,
                    edge_ids=edge_ids,
                )

    for contract in release.contracts:
        linked_award_id = award_id_by_ocds.get(contract.award_ref) if contract.award_ref else None
        meta = {"ocds_contract_id": contract.ocds_contract_id, **(contract.meta or {})}
        contract_id, inserted = _upsert_contract(
            connection,
            award_id=linked_award_id,
            supplier_id=party_ids[contract.supplier_ref],
            agency_id=party_ids[contract.agency_ref],
            ocds_contract_id=contract.ocds_contract_id,
            value_amount=contract.value_amount,
            currency=contract.currency,
            signed_at=contract.signed_at,
            period=contract.period,
            status=contract.status,
            meta=meta,
        )
        result.contract_ids.append(contract_id)
        if inserted:
            result.contracts_inserted += 1
        if provenance is not None:
            _link_subject(
                connection,
                provenance,
                subject_type="contract",
                subject_id=contract_id,
                edge_ids=edge_ids,
            )

    result.provenance_edge_ids = edge_ids
    return result
