"""Finance red-flag rules (E7.2 / spec 0018)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from naijaledger.anomaly import thresholds as T
from naijaledger.anomaly.context import RuleContext
from naijaledger.anomaly.models import FlagDraft, FlagSeverity
from naijaledger.anomaly.util import (
    address_key,
    as_datetime,
    as_int,
    as_uuid,
    is_ngn,
    median_abs_deviation,
    ngn_to_kobo,
)

_COMPETITIVE = frozenset({"open", "selective"})


def evaluate_single_bidder(ctx: RuleContext) -> list[FlagDraft]:
    awards_by_tender: dict[UUID, int] = defaultdict(int)
    for award in ctx.awards:
        tender_id = as_uuid(award.get("tender_id"))
        if tender_id is not None:
            awards_by_tender[tender_id] += 1

    drafts: list[FlagDraft] = []
    for tender in ctx.tenders:
        tender_id = as_uuid(tender.get("id"))
        if tender_id is None:
            continue
        raw_meta = tender.get("meta")
        meta: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
        n_tenderers = as_int(meta.get("numberOfTenderers"))
        method = tender.get("method")
        method_s = str(method).strip().lower() if method is not None else None
        award_count = awards_by_tender.get(tender_id, 0)

        if n_tenderers == 1:
            reason = "numberOfTenderers=1"
        elif n_tenderers is None and method_s in _COMPETITIVE and award_count == 1:
            reason = "competitive method with exactly one award (numberOfTenderers absent)"
        else:
            continue

        drafts.append(
            FlagDraft(
                subject_type="tender",
                subject_id=tender_id,
                rule="single_bidder",
                severity="medium",
                evidence={
                    "summary": f"Single-bidder signal: {reason}",
                    "reason": reason,
                    "method": method_s,
                    "numberOfTenderers": n_tenderers,
                    "award_count": award_count,
                },
                created_by="single_bidder",
            )
        )
    return drafts


def evaluate_short_window(ctx: RuleContext) -> list[FlagDraft]:
    drafts: list[FlagDraft] = []
    for tender in ctx.tenders:
        tender_id = as_uuid(tender.get("id"))
        opens = as_datetime(tender.get("bidding_opens_at"))
        closes = as_datetime(tender.get("bidding_closes_at"))
        if tender_id is None or opens is None or closes is None or closes <= opens:
            continue
        window_days = (closes - opens).total_seconds() / 86400.0
        if window_days >= T.SHORT_WINDOW_DAYS:
            continue
        severity: FlagSeverity = "high" if window_days < T.SHORT_WINDOW_HIGH_DAYS else "medium"
        drafts.append(
            FlagDraft(
                subject_type="tender",
                subject_id=tender_id,
                rule="short_window",
                severity=severity,
                evidence={
                    "summary": (
                        f"Bidding window {window_days:.1f} days "
                        f"(< {T.SHORT_WINDOW_DAYS} day threshold)"
                    ),
                    "opens_at": opens.isoformat(),
                    "closes_at": closes.isoformat(),
                    "window_days": round(window_days, 3),
                    "threshold_days": T.SHORT_WINDOW_DAYS,
                },
                created_by="short_window",
            )
        )
    return drafts


def evaluate_threshold_hugging(ctx: RuleContext) -> list[FlagDraft]:
    drafts: list[FlagDraft] = []
    thresholds_kobo = [ngn_to_kobo(n) for n in T.APPROVAL_THRESHOLDS_NGN]
    for award in ctx.awards:
        award_id = as_uuid(award.get("id"))
        amount = as_int(award.get("value_amount"))
        if award_id is None or amount is None or not is_ngn(award.get("currency")):
            continue
        for threshold in thresholds_kobo:
            hug_band = int(threshold * T.THRESHOLD_HUG_RATIO)
            lower = threshold - hug_band
            if lower < amount <= threshold:
                drafts.append(
                    FlagDraft(
                        subject_type="award",
                        subject_id=award_id,
                        rule="threshold_hugging",
                        severity="medium",
                        evidence={
                            "summary": (
                                f"Award value {amount} kobo hugs threshold "
                                f"{threshold} kobo (within {T.THRESHOLD_HUG_RATIO:.0%})"
                            ),
                            "value_amount": amount,
                            "threshold_kobo": threshold,
                            "hug_band_kobo": hug_band,
                            "hug_ratio": T.THRESHOLD_HUG_RATIO,
                        },
                        created_by="threshold_hugging",
                    )
                )
                break
    return drafts


def evaluate_repeat_winner(ctx: RuleContext) -> list[FlagDraft]:
    tender_agency = {
        tid: agency
        for tender in ctx.tenders
        if (tid := as_uuid(tender.get("id"))) is not None
        and (agency := as_uuid(tender.get("agency_id"))) is not None
    }

    grouped: dict[tuple[UUID, UUID], list[datetime | None]] = defaultdict(list)
    for award in ctx.awards:
        supplier_id = as_uuid(award.get("supplier_id"))
        tender_id = as_uuid(award.get("tender_id"))
        if supplier_id is None or tender_id is None:
            continue
        agency_id = tender_agency.get(tender_id)
        if agency_id is None:
            continue
        grouped[(supplier_id, agency_id)].append(as_datetime(award.get("awarded_at")))

    drafts: list[FlagDraft] = []
    window = timedelta(days=T.REPEAT_WINDOW_DAYS)
    for (supplier_id, agency_id), dates in grouped.items():
        if len(dates) < T.REPEAT_MIN_AWARDS:
            continue
        dated = [d for d in dates if d is not None]
        if dated:
            count = _max_cluster_size(dated, window)
        else:
            # All undated — treat as one window per spec
            count = len(dates)
        if count < T.REPEAT_MIN_AWARDS:
            continue

        drafts.append(
            FlagDraft(
                subject_type="party",
                subject_id=supplier_id,
                rule="repeat_winner",
                severity="medium",
                evidence={
                    "summary": (
                        f"Supplier won {count} awards from the same agency "
                        f"within {T.REPEAT_WINDOW_DAYS} days"
                    ),
                    "supplier_id": str(supplier_id),
                    "agency_id": str(agency_id),
                    "award_count": count,
                    "window_days": T.REPEAT_WINDOW_DAYS,
                },
                created_by="repeat_winner",
            )
        )
    return drafts


def _max_cluster_size(dates: list[Any], window: timedelta) -> int:
    ordered = sorted(dates)
    best = 0
    left = 0
    for right, end in enumerate(ordered):
        while end - ordered[left] > window:
            left += 1
        best = max(best, right - left + 1)
    return best


def evaluate_shared_address(ctx: RuleContext) -> list[FlagDraft]:
    by_key: dict[str, list[UUID]] = defaultdict(list)
    for party in ctx.parties:
        party_id = as_uuid(party.get("id"))
        party_type = str(party.get("party_type") or "").strip().lower()
        if party_id is None or party_type != "company":
            continue
        key = address_key(party.get("address"))
        if key is None:
            continue
        by_key[key].append(party_id)

    drafts: list[FlagDraft] = []
    for key, party_ids in by_key.items():
        unique = sorted(set(party_ids), key=str)
        if len(unique) < 2:
            continue
        # One flag per party in the cluster (subject = party)
        for party_id in unique:
            others = [str(p) for p in unique if p != party_id]
            drafts.append(
                FlagDraft(
                    subject_type="party",
                    subject_id=party_id,
                    rule="shared_address",
                    severity="medium",
                    evidence={
                        "summary": (
                            f"Company shares address with {len(others)} other "
                            f"compan{'ies' if len(others) != 1 else 'y'}"
                        ),
                        "address_key": key,
                        "peer_party_ids": others,
                    },
                    created_by="shared_address",
                )
            )
    return drafts


def evaluate_price_outlier(ctx: RuleContext) -> list[FlagDraft]:
    by_agency: dict[UUID, list[tuple[UUID, int]]] = defaultdict(list)
    for contract in ctx.contracts:
        contract_id = as_uuid(contract.get("id"))
        agency_id = as_uuid(contract.get("agency_id"))
        amount = as_int(contract.get("value_amount"))
        if (
            contract_id is None
            or agency_id is None
            or amount is None
            or not is_ngn(contract.get("currency"))
        ):
            continue
        by_agency[agency_id].append((contract_id, amount))

    drafts: list[FlagDraft] = []
    for agency_id, rows in by_agency.items():
        if len(rows) < T.OUTLIER_MIN_N:
            continue
        values = [amount for _, amount in rows]
        med, mad = median_abs_deviation(values)
        if mad == 0:
            continue
        for contract_id, amount in rows:
            score = abs(amount - med) / mad
            if score <= T.OUTLIER_MAD_K:
                continue
            drafts.append(
                FlagDraft(
                    subject_type="contract",
                    subject_id=contract_id,
                    rule="price_outlier",
                    severity="medium",
                    evidence={
                        "summary": (
                            f"Contract value is a MAD outlier vs agency peers "
                            f"(score {score:.2f} > {T.OUTLIER_MAD_K})"
                        ),
                        "value_amount": amount,
                        "agency_id": str(agency_id),
                        "median": med,
                        "mad": mad,
                        "mad_score": round(score, 3),
                        "sample_size": len(rows),
                    },
                    created_by="price_outlier",
                )
            )
    return drafts


def evaluate_budget_payment_mismatch(ctx: RuleContext) -> list[FlagDraft]:
    payments_by_key: dict[tuple[UUID, int], int] = defaultdict(int)
    for payment in ctx.payments:
        agency_id = as_uuid(payment.get("agency_id"))
        amount = as_int(payment.get("amount"))
        paid_at = as_datetime(payment.get("paid_at"))
        if (
            agency_id is None
            or amount is None
            or paid_at is None
            or not is_ngn(payment.get("currency"))
        ):
            continue
        payments_by_key[(agency_id, paid_at.year)] += amount

    drafts: list[FlagDraft] = []
    for line in ctx.budget_lines:
        line_id = as_uuid(line.get("id"))
        agency_id = as_uuid(line.get("agency_id"))
        fiscal_year = as_int(line.get("fiscal_year"))
        if line_id is None or agency_id is None or fiscal_year is None:
            continue
        if not is_ngn(line.get("currency")):
            continue
        paid = payments_by_key.get((agency_id, fiscal_year), 0)
        if paid <= 0:
            continue
        utilised = as_int(line.get("utilised_amount"))
        allocated = as_int(line.get("allocated_amount"))
        if utilised is not None:
            cap = utilised
            cap_field = "utilised_amount"
        elif allocated is not None:
            cap = allocated
            cap_field = "allocated_amount"
        else:
            continue
        limit = int(cap * (1 + T.MISMATCH_TOLERANCE))
        if paid <= limit:
            continue
        drafts.append(
            FlagDraft(
                subject_type="budget_line",
                subject_id=line_id,
                rule="budget_payment_mismatch",
                severity="high",
                evidence={
                    "summary": (
                        f"Payments {paid} kobo exceed {cap_field} {cap} kobo "
                        f"by more than {T.MISMATCH_TOLERANCE:.0%} tolerance"
                    ),
                    "payments_sum": paid,
                    "cap": cap,
                    "cap_field": cap_field,
                    "limit": limit,
                    "fiscal_year": fiscal_year,
                    "agency_id": str(agency_id),
                    "tolerance": T.MISMATCH_TOLERANCE,
                },
                created_by="budget_payment_mismatch",
            )
        )
    return drafts


class SingleBidderRule:
    id = "single_bidder"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        return evaluate_single_bidder(ctx)


class ShortWindowRule:
    id = "short_window"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        return evaluate_short_window(ctx)


class ThresholdHuggingRule:
    id = "threshold_hugging"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        return evaluate_threshold_hugging(ctx)


class RepeatWinnerRule:
    id = "repeat_winner"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        return evaluate_repeat_winner(ctx)


class SharedAddressRule:
    id = "shared_address"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        return evaluate_shared_address(ctx)


class PriceOutlierRule:
    id = "price_outlier"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        return evaluate_price_outlier(ctx)


class BudgetPaymentMismatchRule:
    id = "budget_payment_mismatch"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        return evaluate_budget_payment_mismatch(ctx)
