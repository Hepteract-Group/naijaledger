"""Anomaly backtest metrics (E7.3 / spec 0019)."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from naijaledger.anomaly.context import RuleContext
from naijaledger.anomaly.models import FlagDraft
from naijaledger.anomaly.runner import AnomalyRule

FlagKey = tuple[str, str, UUID]

MIN_PRECISION = 0.80
MIN_RECALL = 0.80
MIN_RULE_PRECISION = 0.50
MIN_RULE_RECALL = 0.50


class ExpectedFlag(BaseModel):
    rule: str
    subject_type: str
    subject_key: str


class BacktestCase(BaseModel):
    context: RuleContext
    expected: list[ExpectedFlag] = Field(default_factory=list)
    subject_keys: dict[str, UUID] = Field(default_factory=dict)


class RuleScore(BaseModel):
    rule: str
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


class BacktestReport(BaseModel):
    overall: RuleScore
    by_rule: list[RuleScore]
    passed: bool
    min_precision: float
    min_recall: float
    min_rule_precision: float
    min_rule_recall: float


def score_sets(predicted: set[FlagKey], expected: set[FlagKey], *, rule: str) -> RuleScore:
    tp = len(predicted & expected)
    fp = len(predicted - expected)
    fn = len(expected - predicted)
    empty = tp == 0 and fp == 0 and fn == 0
    precision = 1.0 if empty else (tp / (tp + fp) if (tp + fp) else 0.0)
    recall = 1.0 if empty else (tp / (tp + fn) if (tp + fn) else 0.0)
    if empty:
        f1 = 1.0
    elif precision + recall == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall)
    return RuleScore(
        rule=rule,
        tp=tp,
        fp=fp,
        fn=fn,
        precision=precision,
        recall=recall,
        f1=f1,
    )


def draft_key(draft: FlagDraft) -> FlagKey:
    return (draft.rule, draft.subject_type, draft.subject_id)


def expected_key(label: ExpectedFlag, subject_keys: dict[str, UUID]) -> FlagKey:
    subject_id = subject_keys[label.subject_key]
    return (label.rule, label.subject_type, subject_id)


def run_backtest(
    case: BacktestCase,
    rules: list[AnomalyRule],
    *,
    min_precision: float = MIN_PRECISION,
    min_recall: float = MIN_RECALL,
    min_rule_precision: float = MIN_RULE_PRECISION,
    min_rule_recall: float = MIN_RULE_RECALL,
) -> BacktestReport:
    predicted: set[FlagKey] = set()
    for rule in rules:
        for draft in rule.evaluate(case.context):
            predicted.add(draft_key(draft))

    expected: set[FlagKey] = {expected_key(label, case.subject_keys) for label in case.expected}

    rule_ids = sorted({key[0] for key in predicted | expected} | {rule.id for rule in rules})
    by_rule: list[RuleScore] = []
    for rule_id in rule_ids:
        by_rule.append(
            score_sets(
                {k for k in predicted if k[0] == rule_id},
                {k for k in expected if k[0] == rule_id},
                rule=rule_id,
            )
        )

    overall = score_sets(predicted, expected, rule="*")
    passed = overall.precision >= min_precision and overall.recall >= min_recall
    expected_counts: dict[str, int] = {}
    for label in case.expected:
        expected_counts[label.rule] = expected_counts.get(label.rule, 0) + 1
    for score in by_rule:
        if expected_counts.get(score.rule, 0) < 1:
            continue
        if score.precision < min_rule_precision or score.recall < min_rule_recall:
            passed = False

    return BacktestReport(
        overall=overall,
        by_rule=by_rule,
        passed=passed,
        min_precision=min_precision,
        min_recall=min_recall,
        min_rule_precision=min_rule_precision,
        min_rule_recall=min_rule_recall,
    )
