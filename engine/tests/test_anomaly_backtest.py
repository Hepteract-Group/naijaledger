from uuid import uuid4

from naijaledger.anomaly.backtest import (
    BacktestCase,
    ExpectedFlag,
    run_backtest,
    score_sets,
)
from naijaledger.anomaly.backtest_cli import main as backtest_main
from naijaledger.anomaly.context import RuleContext
from naijaledger.anomaly.corpus import load_backtest_case
from naijaledger.anomaly.models import FlagDraft
from naijaledger.anomaly.runner import production_rules


def test_score_sets_fp_lowers_precision() -> None:
    sid = uuid4()
    predicted = {("smoke", "tender", sid), ("smoke", "tender", uuid4())}
    expected = {("smoke", "tender", sid)}
    score = score_sets(predicted, expected, rule="smoke")
    assert score.tp == 1
    assert score.fp == 1
    assert score.fn == 0
    assert score.precision == 0.5


def test_corpus_covers_all_production_rules() -> None:
    case = load_backtest_case()
    expected_rules = {label.rule for label in case.expected}
    prod = {rule.id for rule in production_rules()}
    assert prod <= expected_rules
    assert len(prod) == 7


def test_backtest_passes_on_corpus() -> None:
    report = run_backtest(load_backtest_case(), production_rules())
    assert report.passed, report.model_dump()
    assert report.overall.precision >= report.min_precision
    assert report.overall.recall >= report.min_recall
    for score in report.by_rule:
        if score.rule == "*" or score.tp + score.fn == 0:
            continue
        assert score.precision >= report.min_rule_precision
        assert score.recall >= report.min_rule_recall


def test_backtest_does_not_need_db() -> None:
    # Pure in-memory: constructing and scoring never touches SQL.
    case = load_backtest_case()
    assert isinstance(case.context, RuleContext)
    report = run_backtest(case, production_rules())
    assert report.overall.tp >= 7


def test_cli_exits_zero(capsys) -> None:
    assert backtest_main([]) == 0
    out = capsys.readouterr().out
    assert "passed=True" in out


class _AlwaysFlagRule:
    id = "single_bidder"

    def evaluate(self, ctx: RuleContext) -> list[FlagDraft]:
        # Emit an extra FP on a random subject to force precision drop if used alone
        return [
            FlagDraft(
                subject_type="tender",
                subject_id=uuid4(),
                rule="single_bidder",
                severity="medium",
                evidence={"summary": "noise"},
                created_by="single_bidder",
            )
        ]


def test_run_backtest_with_extra_fp_fails_gate() -> None:
    case = BacktestCase(
        context=RuleContext(),
        expected=[
            ExpectedFlag(rule="single_bidder", subject_type="tender", subject_key="t1"),
        ],
        subject_keys={"t1": uuid4()},
    )
    report = run_backtest(case, [_AlwaysFlagRule()], min_precision=0.99, min_recall=0.99)
    assert report.overall.fp >= 1
    assert report.passed is False
