from typing import Any, TypedDict

from naijaledger.extractions.types import ExtractionDerivation, ExtractionMethod, ExtractionStatus


class Block(TypedDict):
    kind: str  # "table" | "text" | "record"
    payload: dict[str, Any]
    page: int | None
    region: dict[str, float] | None


class ExtractionOutcome(TypedDict):
    method: ExtractionMethod
    method_version: str
    derivation: ExtractionDerivation
    confidence: float
    status: ExtractionStatus
    content_type: str
    content_type_conf: float
    blocks: list[Block]
