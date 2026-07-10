"""Unit tests for E7.2 red-flag rules (spec 0018)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from naijaledger.anomaly.context import RuleContext
from naijaledger.anomaly.rules import (
    evaluate_budget_payment_mismatch,
    evaluate_price_outlier,
    evaluate_repeat_winner,
    evaluate_shared_address,
    evaluate_short_window,
    evaluate_single_bidder,
    evaluate_threshold_hugging,
)
from naijaledger.anomaly.runner import production_rules, run_anomaly_rules
from naijaledger.anomaly.thresholds import APPROVAL_THRESHOLDS_NGN, THRESHOLD_HUG_RATIO
from naijaledger.anomaly.util import ngn_to_kobo
from naijaledger.finance.ocds import normalize_ocds_release


def test_production_rules_ids() -> None:
    ids = [rule.id for rule in production_rules()]
    assert ids == [
        "single_bidder",
        "short_window",
        "threshold_hugging",
        "repeat_winner",
        "shared_address",
        "price_outlier",
        "budget_payment_mismatch",
    ]


def test_empty_context_emits_nothing() -> None:
    ctx = RuleContext()
    assert evaluate_single_bidder(ctx) == []
    assert evaluate_short_window(ctx) == []
    assert evaluate_threshold_hugging(ctx) == []
    assert evaluate_repeat_winner(ctx) == []
    assert evaluate_shared_address(ctx) == []
    assert evaluate_price_outlier(ctx) == []
    assert evaluate_budget_payment_mismatch(ctx) == []


def test_single_bidder_from_number_of_tenderers() -> None:
    tender_id = uuid4()
    ctx = RuleContext(
        tenders=[
            {
                "id": tender_id,
                "method": "open",
                "meta": {"numberOfTenderers": 1},
            }
        ]
    )
    drafts = evaluate_single_bidder(ctx)
    assert len(drafts) == 1
    assert drafts[0].rule == "single_bidder"
    assert drafts[0].subject_id == tender_id
    assert "summary" in drafts[0].evidence


def test_single_bidder_proxy_competitive_one_award() -> None:
    tender_id = uuid4()
    ctx = RuleContext(
        tenders=[{"id": tender_id, "method": "open", "meta": {}}],
        awards=[{"id": uuid4(), "tender_id": tender_id, "supplier_id": uuid4()}],
    )
    assert len(evaluate_single_bidder(ctx)) == 1


def test_short_window_high_severity() -> None:
    tender_id = uuid4()
    opens = datetime(2024, 1, 1, tzinfo=UTC)
    closes = opens + timedelta(days=2)
    ctx = RuleContext(
        tenders=[
            {
                "id": tender_id,
                "bidding_opens_at": opens,
                "bidding_closes_at": closes,
            }
        ]
    )
    drafts = evaluate_short_window(ctx)
    assert len(drafts) == 1
    assert drafts[0].severity == "high"


def test_threshold_hugging() -> None:
    threshold = ngn_to_kobo(APPROVAL_THRESHOLDS_NGN[0])
    hug = int(threshold * THRESHOLD_HUG_RATIO)
    amount = threshold - hug // 2
    award_id = uuid4()
    ctx = RuleContext(
        awards=[
            {
                "id": award_id,
                "value_amount": amount,
                "currency": "NGN",
            }
        ]
    )
    drafts = evaluate_threshold_hugging(ctx)
    assert len(drafts) == 1
    assert drafts[0].subject_id == award_id


def test_repeat_winner() -> None:
    supplier = uuid4()
    agency = uuid4()
    tender_ids = [uuid4() for _ in range(3)]
    base = datetime(2024, 6, 1, tzinfo=UTC)
    ctx = RuleContext(
        tenders=[{"id": tid, "agency_id": agency} for tid in tender_ids],
        awards=[
            {
                "id": uuid4(),
                "tender_id": tid,
                "supplier_id": supplier,
                "awarded_at": base + timedelta(days=i * 10),
            }
            for i, tid in enumerate(tender_ids)
        ],
    )
    drafts = evaluate_repeat_winner(ctx)
    assert len(drafts) == 1
    assert drafts[0].subject_id == supplier
    assert drafts[0].subject_type == "party"


def test_shared_address() -> None:
    a, b = uuid4(), uuid4()
    addr = {"street": "12 Broad St", "city": "Lagos", "postalCode": "100001"}
    ctx = RuleContext(
        parties=[
            {"id": a, "party_type": "company", "address": addr},
            {"id": b, "party_type": "company", "address": dict(addr)},
        ]
    )
    drafts = evaluate_shared_address(ctx)
    assert {d.subject_id for d in drafts} == {a, b}


def test_price_outlier_and_mad_zero() -> None:
    agency = uuid4()
    # Five equal values → MAD 0 → no flags
    equal = RuleContext(
        contracts=[
            {
                "id": uuid4(),
                "agency_id": agency,
                "value_amount": 1_000_000,
                "currency": "NGN",
            }
            for _ in range(5)
        ]
    )
    assert evaluate_price_outlier(equal) == []

    # Varied peers so MAD > 0, plus one extreme outlier
    outlier_id = uuid4()
    peers = [
        {"id": uuid4(), "agency_id": agency, "value_amount": v, "currency": "NGN"}
        for v in (100, 110, 120, 130, 140)
    ]
    peers.append(
        {
            "id": outlier_id,
            "agency_id": agency,
            "value_amount": 50_000,
            "currency": "NGN",
        }
    )
    drafts = evaluate_price_outlier(RuleContext(contracts=peers))
    assert any(d.subject_id == outlier_id for d in drafts)


def test_budget_payment_mismatch() -> None:
    agency = uuid4()
    line_id = uuid4()
    ctx = RuleContext(
        budget_lines=[
            {
                "id": line_id,
                "agency_id": agency,
                "fiscal_year": 2024,
                "utilised_amount": 1_000_000,
                "currency": "NGN",
            }
        ],
        payments=[
            {
                "id": uuid4(),
                "agency_id": agency,
                "amount": 1_500_000,
                "currency": "NGN",
                "paid_at": datetime(2024, 3, 1, tzinfo=UTC),
            }
        ],
    )
    drafts = evaluate_budget_payment_mismatch(ctx)
    assert len(drafts) == 1
    assert drafts[0].severity == "high"
    assert drafts[0].subject_id == line_id


def test_ocds_number_of_tenderers_in_meta() -> None:
    release = {
        "ocid": "ocds-test-not",
        "buyer": {"id": "b1", "name": "Agency"},
        "parties": [
            {"id": "b1", "name": "Agency", "roles": ["buyer"]},
            {"id": "s1", "name": "Supplier", "roles": ["supplier"]},
        ],
        "tender": {
            "id": "t1",
            "title": "Widgets",
            "procurementMethod": "open",
            "numberOfTenderers": 1,
            "procuringEntity": {"id": "b1", "name": "Agency"},
        },
        "awards": [],
        "contracts": [],
    }
    normalized = normalize_ocds_release(release)
    assert normalized.tender is not None
    assert normalized.tender.meta is not None
    assert normalized.tender.meta["numberOfTenderers"] == 1


def test_run_production_rules_on_empty_db(db_connection) -> None:
    result = run_anomaly_rules(db_connection, production_rules())
    assert result.rules_run == [rule.id for rule in production_rules()]
    assert result.drafts == 0
    assert result.upserted == 0
