from uuid import UUID

from sqlalchemy.engine import Connection

from naijaledger.extract.detect import detect_content_type
from naijaledger.extract.route import DEFAULT_MAGIKA_MIN_CONFIDENCE, decide_extraction_route
from naijaledger.extract.types import RouteDecision
from naijaledger.extractions.models import Extraction, ExtractionCreate
from naijaledger.extractions.service import create_extraction
from naijaledger.extractions.types import ExtractionMethod
from naijaledger.sources.types import SourceFormat

ROUTER_METHOD_VERSION = "magika-router-1"

_FORMAT_TO_METHOD: dict[SourceFormat, ExtractionMethod] = {
    "xlsx": "xlsx",
    "csv": "csv",
    "json": "json",
    "pdf": "pdf_text",
    "html": "pdf_text",
    "image": "ocr",
}


def _method_for_decision(decision: RouteDecision) -> ExtractionMethod:
    sniffed = decision["sniffed_format"]
    if sniffed is not None and sniffed in _FORMAT_TO_METHOD:
        return _FORMAT_TO_METHOD[sniffed]
    return "pdf_text"


def _ambiguous_confidence(content_type_conf: float) -> float:
    return min(content_type_conf, 0.999)


def route_document_bytes(
    *,
    data: bytes,
    declared_format: SourceFormat,
    min_confidence: float = DEFAULT_MAGIKA_MIN_CONFIDENCE,
) -> RouteDecision:
    detection = detect_content_type(data)
    return decide_extraction_route(
        detection=detection,
        declared_format=declared_format,
        min_confidence=min_confidence,
    )


def record_quarantine(
    connection: Connection,
    *,
    document_id: UUID,
    decision: RouteDecision,
) -> Extraction:
    """Persist a quarantine row so low-confidence / mismatched docs are visible."""
    if decision["kind"] != "quarantine":
        msg = f"record_quarantine requires kind=quarantine, got {decision['kind']}"
        raise ValueError(msg)

    return create_extraction(
        connection,
        ExtractionCreate(
            document_id=document_id,
            method=_method_for_decision(decision),
            method_version=ROUTER_METHOD_VERSION,
            derivation="ambiguous",
            confidence=_ambiguous_confidence(decision["content_type_conf"]),
            ok=False,
            payload={
                "blocks": [],
                "quarantine": {
                    "reason": decision["reason"],
                    "sniffed_format": decision["sniffed_format"],
                },
            },
            content_type=decision["content_type"],
            content_type_conf=decision["content_type_conf"],
            status="quarantined",
        ),
    )


def record_unsupported(
    connection: Connection,
    *,
    document_id: UUID,
    decision: RouteDecision,
) -> Extraction:
    if decision["kind"] != "unsupported":
        msg = f"record_unsupported requires kind=unsupported, got {decision['kind']}"
        raise ValueError(msg)

    return create_extraction(
        connection,
        ExtractionCreate(
            document_id=document_id,
            method=_method_for_decision(decision),
            method_version=ROUTER_METHOD_VERSION,
            derivation="ambiguous",
            confidence=_ambiguous_confidence(decision["content_type_conf"]),
            ok=True,
            payload={
                "blocks": [],
                "unsupported": {
                    "reason": decision["reason"],
                    "sniffed_format": decision["sniffed_format"],
                },
            },
            content_type=decision["content_type"],
            content_type_conf=decision["content_type_conf"],
            status="unsupported",
        ),
    )
