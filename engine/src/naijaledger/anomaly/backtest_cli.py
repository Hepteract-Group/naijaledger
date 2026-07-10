"""CLI: run anomaly backtest on the labeled corpus."""

from __future__ import annotations

import argparse
import sys

from naijaledger.anomaly.backtest import run_backtest
from naijaledger.anomaly.corpus import load_backtest_case
from naijaledger.anomaly.runner import production_rules


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NaijaLedger anomaly backtest (E7.3)")
    parser.add_argument("--json", action="store_true", help="Print full report JSON")
    args = parser.parse_args(argv)

    report = run_backtest(load_backtest_case(), production_rules())
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(
            f"passed={report.passed} precision={report.overall.precision:.3f} "
            f"recall={report.overall.recall:.3f} f1={report.overall.f1:.3f} "
            f"tp={report.overall.tp} fp={report.overall.fp} fn={report.overall.fn}"
        )
        for score in report.by_rule:
            print(
                f"  {score.rule}: p={score.precision:.2f} r={score.recall:.2f} "
                f"tp={score.tp} fp={score.fp} fn={score.fn}"
            )
    return 0 if report.passed else 1


def run() -> None:
    sys.exit(main())


if __name__ == "__main__":
    run()
