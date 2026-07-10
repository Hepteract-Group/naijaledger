"""Labeled synthetic corpus for anomaly backtest (spec 0019).

Scenarios (true positive + near-miss true negative per rule):
- single_bidder: tender with numberOfTenderers=1 vs tender with 3
- short_window: 2-day window vs 14-day window
- threshold_hugging: award just under 5M NGN vs well below
- repeat_winner: 3 awards same agency in window vs 2
- shared_address: two companies same address vs unique addresses
- price_outlier: extreme contract vs peers in band
- budget_payment_mismatch: payments >> utilised vs within tolerance
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

from naijaledger.anomaly.backtest import BacktestCase, ExpectedFlag
from naijaledger.anomaly.context import RuleContext
from naijaledger.anomaly.thresholds import APPROVAL_THRESHOLDS_NGN, THRESHOLD_HUG_RATIO
from naijaledger.anomaly.util import ngn_to_kobo

_NS = NAMESPACE_URL


def _uid(key: str) -> UUID:
    return uuid5(_NS, f"naijaledger:anomaly-backtest:{key}")


def load_backtest_case() -> BacktestCase:
    keys = {
        "tender_single": _uid("tender_single"),
        "tender_multi": _uid("tender_multi"),
        "tender_short": _uid("tender_short"),
        "tender_long": _uid("tender_long"),
        "award_hug": _uid("award_hug"),
        "award_safe": _uid("award_safe"),
        "supplier_repeat": _uid("supplier_repeat"),
        "supplier_once": _uid("supplier_once"),
        "supplier_hug": _uid("supplier_hug"),
        "agency_a": _uid("agency_a"),
        "tender_r1": _uid("tender_r1"),
        "tender_r2": _uid("tender_r2"),
        "tender_r3": _uid("tender_r3"),
        "tender_once": _uid("tender_once"),
        "party_share_a": _uid("party_share_a"),
        "party_share_b": _uid("party_share_b"),
        "party_alone": _uid("party_alone"),
        "contract_outlier": _uid("contract_outlier"),
        "contract_p1": _uid("contract_p1"),
        "contract_p2": _uid("contract_p2"),
        "contract_p3": _uid("contract_p3"),
        "contract_p4": _uid("contract_p4"),
        "contract_p5": _uid("contract_p5"),
        "budget_over": _uid("budget_over"),
        "budget_ok": _uid("budget_ok"),
        "agency_budget": _uid("agency_budget"),
        "agency_budget_ok": _uid("agency_budget_ok"),
    }

    threshold = ngn_to_kobo(APPROVAL_THRESHOLDS_NGN[0])
    hug_amount = threshold - int(threshold * THRESHOLD_HUG_RATIO) // 2
    safe_amount = threshold // 2

    opens = datetime(2024, 1, 1, tzinfo=UTC)
    base_award = datetime(2024, 6, 1, tzinfo=UTC)

    ctx = RuleContext(
        tenders=[
            {
                "id": keys["tender_single"],
                "method": "open",
                "meta": {"numberOfTenderers": 1},
                "agency_id": keys["agency_a"],
            },
            {
                "id": keys["tender_multi"],
                "method": "open",
                "meta": {"numberOfTenderers": 3},
                "agency_id": keys["agency_a"],
            },
            {
                "id": keys["tender_short"],
                "bidding_opens_at": opens,
                "bidding_closes_at": opens + timedelta(days=2),
                "agency_id": keys["agency_a"],
            },
            {
                "id": keys["tender_long"],
                "bidding_opens_at": opens,
                "bidding_closes_at": opens + timedelta(days=14),
                "agency_id": keys["agency_a"],
            },
            {"id": keys["tender_r1"], "agency_id": keys["agency_a"]},
            {"id": keys["tender_r2"], "agency_id": keys["agency_a"]},
            {"id": keys["tender_r3"], "agency_id": keys["agency_a"]},
            {"id": keys["tender_once"], "agency_id": keys["agency_a"]},
        ],
        awards=[
            {
                "id": keys["award_hug"],
                "value_amount": hug_amount,
                "currency": "NGN",
                "tender_id": keys["tender_multi"],
                "supplier_id": keys["supplier_hug"],
            },
            {
                "id": keys["award_safe"],
                "value_amount": safe_amount,
                "currency": "NGN",
                "tender_id": keys["tender_multi"],
                "supplier_id": keys["supplier_hug"],
            },
            {
                "id": _uid("award_r1"),
                "tender_id": keys["tender_r1"],
                "supplier_id": keys["supplier_repeat"],
                "awarded_at": base_award,
            },
            {
                "id": _uid("award_r2"),
                "tender_id": keys["tender_r2"],
                "supplier_id": keys["supplier_repeat"],
                "awarded_at": base_award + timedelta(days=30),
            },
            {
                "id": _uid("award_r3"),
                "tender_id": keys["tender_r3"],
                "supplier_id": keys["supplier_repeat"],
                "awarded_at": base_award + timedelta(days=60),
            },
            {
                "id": _uid("award_once"),
                "tender_id": keys["tender_once"],
                "supplier_id": keys["supplier_once"],
                "awarded_at": base_award,
            },
            {
                "id": _uid("award_once2"),
                "tender_id": keys["tender_once"],
                "supplier_id": keys["supplier_once"],
                "awarded_at": base_award + timedelta(days=10),
            },
        ],
        parties=[
            {
                "id": keys["party_share_a"],
                "party_type": "company",
                "address": {"street": "1 Shared Rd", "city": "Abuja", "postalCode": "900001"},
            },
            {
                "id": keys["party_share_b"],
                "party_type": "company",
                "address": {"street": "1 Shared Rd", "city": "Abuja", "postalCode": "900001"},
            },
            {
                "id": keys["party_alone"],
                "party_type": "company",
                "address": {"street": "9 Solo Ave", "city": "Abuja", "postalCode": "900002"},
            },
        ],
        contracts=[
            {
                "id": keys["contract_outlier"],
                "agency_id": keys["agency_a"],
                "value_amount": 50_000,
                "currency": "NGN",
            },
            {
                "id": keys["contract_p1"],
                "agency_id": keys["agency_a"],
                "value_amount": 100,
                "currency": "NGN",
            },
            {
                "id": keys["contract_p2"],
                "agency_id": keys["agency_a"],
                "value_amount": 110,
                "currency": "NGN",
            },
            {
                "id": keys["contract_p3"],
                "agency_id": keys["agency_a"],
                "value_amount": 120,
                "currency": "NGN",
            },
            {
                "id": keys["contract_p4"],
                "agency_id": keys["agency_a"],
                "value_amount": 130,
                "currency": "NGN",
            },
            {
                "id": keys["contract_p5"],
                "agency_id": keys["agency_a"],
                "value_amount": 140,
                "currency": "NGN",
            },
        ],
        budget_lines=[
            {
                "id": keys["budget_over"],
                "agency_id": keys["agency_budget"],
                "fiscal_year": 2024,
                "utilised_amount": 1_000_000,
                "currency": "NGN",
            },
            {
                "id": keys["budget_ok"],
                "agency_id": keys["agency_budget_ok"],
                "fiscal_year": 2024,
                "utilised_amount": 1_000_000,
                "currency": "NGN",
            },
        ],
        payments=[
            {
                "id": _uid("pay_over"),
                "agency_id": keys["agency_budget"],
                "amount": 1_500_000,
                "currency": "NGN",
                "paid_at": datetime(2024, 4, 1, tzinfo=UTC),
            },
            {
                "id": _uid("pay_ok"),
                "agency_id": keys["agency_budget_ok"],
                "amount": 1_050_000,
                "currency": "NGN",
                "paid_at": datetime(2024, 4, 1, tzinfo=UTC),
            },
        ],
    )

    expected = [
        ExpectedFlag(rule="single_bidder", subject_type="tender", subject_key="tender_single"),
        ExpectedFlag(rule="short_window", subject_type="tender", subject_key="tender_short"),
        ExpectedFlag(rule="threshold_hugging", subject_type="award", subject_key="award_hug"),
        ExpectedFlag(rule="repeat_winner", subject_type="party", subject_key="supplier_repeat"),
        ExpectedFlag(rule="shared_address", subject_type="party", subject_key="party_share_a"),
        ExpectedFlag(rule="shared_address", subject_type="party", subject_key="party_share_b"),
        ExpectedFlag(rule="price_outlier", subject_type="contract", subject_key="contract_outlier"),
        ExpectedFlag(
            rule="budget_payment_mismatch",
            subject_type="budget_line",
            subject_key="budget_over",
        ),
    ]

    return BacktestCase(context=ctx, expected=expected, subject_keys=keys)
