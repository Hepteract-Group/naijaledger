import json
from typing import Any

from naijaledger.extract.outcome import Block, ExtractionOutcome
from naijaledger.extractions.types import DETERMINISTIC_CONFIDENCE

JSON_METHOD_VERSION = "stdlib-json-1"


def parse_json(
    data: bytes,
    *,
    content_type: str,
    content_type_conf: float,
) -> ExtractionOutcome:
    try:
        parsed: Any = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ExtractionOutcome(
            method="json",
            method_version=JSON_METHOD_VERSION,
            derivation="extracted",
            confidence=DETERMINISTIC_CONFIDENCE,
            status="failed",
            content_type=content_type,
            content_type_conf=content_type_conf,
            blocks=[],
        )

    blocks: list[Block] = []
    if isinstance(parsed, list):
        for index, item in enumerate(parsed):
            blocks.append(
                Block(
                    kind="record",
                    payload={"index": index, "value": item},
                    page=None,
                    region=None,
                )
            )
    else:
        blocks.append(
            Block(
                kind="record",
                payload={"value": parsed},
                page=None,
                region=None,
            )
        )

    return ExtractionOutcome(
        method="json",
        method_version=JSON_METHOD_VERSION,
        derivation="extracted",
        confidence=DETERMINISTIC_CONFIDENCE,
        status="parsed" if blocks else "failed",
        content_type=content_type,
        content_type_conf=content_type_conf,
        blocks=blocks,
    )
