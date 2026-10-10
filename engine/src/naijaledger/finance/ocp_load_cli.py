"""CLI: load Open Contracting Partnership state bulk awards (spec 0041)."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from naijaledger.archive.storage import create_minio_client
from naijaledger.config import load_settings
from naijaledger.db.connection import create_db_engine
from naijaledger.finance.ocp_load import format_summary_line, run_load_job
from naijaledger.finance.ocp_registry import default_licences_dir

logger = logging.getLogger("naijaledger.finance.ocp_load")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load OCP Data Registry state full.jsonl.gz awards (spec 0041)",
    )
    parser.add_argument(
        "--licences-dir",
        type=Path,
        default=None,
        help="Directory of signed ocp-state-*.md records (default: docs/licences)",
    )
    parser.add_argument(
        "--max-releases",
        type=int,
        default=None,
        help="Cap releases loaded per publication (fixture / sample runs)",
    )
    return parser


def run(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO)
    args = build_parser().parse_args(argv)
    settings = load_settings()
    engine = create_db_engine()
    licences_dir = args.licences_dir or default_licences_dir()
    minio = create_minio_client(settings)
    summaries = run_load_job(
        engine,
        minio_client=minio,
        bucket=settings.minio_bucket,
        licences_dir=licences_dir,
        max_releases=args.max_releases,
    )
    print(
        "state\tpublication_id\tretrieved_on\treleases\t"
        "awards_written\tawards_positive_amount\tskip_reason"
    )
    for summary in summaries:
        line = format_summary_line(summary)
        print(line)
        logger.info("%s", line)


if __name__ == "__main__":
    run()
