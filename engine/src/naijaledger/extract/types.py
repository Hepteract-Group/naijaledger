from typing import Literal, TypedDict

from naijaledger.extractions.types import ExtractionMethod
from naijaledger.sources.types import SourceFormat

RouteKind = Literal["pass1", "unsupported", "quarantine"]


class ContentTypeDetection(TypedDict):
    label: str
    mime_type: str
    confidence: float


class RouteDecision(TypedDict):
    kind: RouteKind
    method: ExtractionMethod | None
    content_type: str
    content_type_conf: float
    sniffed_format: SourceFormat | None
    reason: str | None
