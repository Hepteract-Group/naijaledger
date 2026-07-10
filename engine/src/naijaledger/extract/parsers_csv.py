import csv
from io import StringIO

from naijaledger.extract.outcome import Block, ExtractionOutcome
from naijaledger.extractions.types import DETERMINISTIC_CONFIDENCE

CSV_METHOD_VERSION = "stdlib-csv-1"


def parse_csv(
    data: bytes,
    *,
    content_type: str,
    content_type_conf: float,
) -> ExtractionOutcome:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.reader(StringIO(text))
    rows = [list(row) for row in reader if any(cell.strip() for cell in row)]
    blocks: list[Block] = []
    if rows:
        blocks.append(
            Block(
                kind="table",
                payload={"rows": rows},
                page=None,
                region=None,
            )
        )

    return ExtractionOutcome(
        method="csv",
        method_version=CSV_METHOD_VERSION,
        derivation="extracted",
        confidence=DETERMINISTIC_CONFIDENCE,
        status="parsed" if blocks else "failed",
        content_type=content_type,
        content_type_conf=content_type_conf,
        blocks=blocks,
    )
