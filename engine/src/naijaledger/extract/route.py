from naijaledger.extract.types import ContentTypeDetection, RouteDecision
from naijaledger.extractions.types import ExtractionMethod
from naijaledger.sources.types import SourceFormat

# Magika labels we can send to Pass 1 deterministic parsers.
_LABEL_TO_FORMAT: dict[str, SourceFormat] = {
    "pdf": "pdf",
    "xlsx": "xlsx",
    "xls": "xlsx",
    "csv": "csv",
    "json": "json",
    "html": "html",
    "htm": "html",
    "jpeg": "image",
    "jpg": "image",
    "png": "image",
    "webp": "image",
    "gif": "image",
}

_FORMAT_TO_METHOD: dict[SourceFormat, ExtractionMethod] = {
    "xlsx": "xlsx",
    "csv": "csv",
    "json": "json",
    "pdf": "pdf_text",
}

# Pass 1 supported artifact formats (not catalog HTML / images).
_PASS1_FORMATS: frozenset[SourceFormat] = frozenset({"pdf", "xlsx", "csv", "json"})

DEFAULT_MAGIKA_MIN_CONFIDENCE = 0.5


def format_from_magika_label(label: str) -> SourceFormat | None:
    return _LABEL_TO_FORMAT.get(label.lower())


def decide_extraction_route(
    *,
    detection: ContentTypeDetection,
    declared_format: SourceFormat,
    min_confidence: float = DEFAULT_MAGIKA_MIN_CONFIDENCE,
) -> RouteDecision:
    content_type = detection["mime_type"] or detection["label"]
    confidence = detection["confidence"]
    sniffed = format_from_magika_label(detection["label"])

    if confidence < min_confidence:
        return RouteDecision(
            kind="quarantine",
            method=None,
            content_type=content_type,
            content_type_conf=confidence,
            sniffed_format=sniffed,
            reason="low_confidence",
        )

    if sniffed is None:
        return RouteDecision(
            kind="unsupported",
            method=None,
            content_type=content_type,
            content_type_conf=confidence,
            sniffed_format=None,
            reason=f"unknown_label:{detection['label']}",
        )

    if sniffed != declared_format:
        return RouteDecision(
            kind="quarantine",
            method=None,
            content_type=content_type,
            content_type_conf=confidence,
            sniffed_format=sniffed,
            reason=f"format_mismatch:declared={declared_format},sniffed={sniffed}",
        )

    if sniffed not in _PASS1_FORMATS:
        return RouteDecision(
            kind="unsupported",
            method=None,
            content_type=content_type,
            content_type_conf=confidence,
            sniffed_format=sniffed,
            reason=f"unsupported_pass1:{sniffed}",
        )

    return RouteDecision(
        kind="pass1",
        method=_FORMAT_TO_METHOD[sniffed],
        content_type=content_type,
        content_type_conf=confidence,
        sniffed_format=sniffed,
        reason=None,
    )
