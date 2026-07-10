from collections.abc import Callable
from typing import TypedDict
from uuid import UUID

from sqlalchemy.engine import Connection

from naijaledger.documents.models import Document
from naijaledger.extract.outcome import ExtractionOutcome
from naijaledger.extract.parsers_csv import parse_csv
from naijaledger.extract.parsers_json import parse_json
from naijaledger.extract.parsers_pdf import parse_pdf
from naijaledger.extract.parsers_xlsx import parse_xlsx
from naijaledger.extract.route import DEFAULT_MAGIKA_MIN_CONFIDENCE
from naijaledger.extract.router import route_document_bytes
from naijaledger.extractions.models import ExtractionCreate, ProvenanceEdgeCreate
from naijaledger.extractions.service import create_extraction, create_provenance_edge
from naijaledger.extractions.types import ExtractionMethod

Pass2Fn = Callable[[Document, bytes, ExtractionOutcome], ExtractionOutcome | None]


class ExtractPersistResult(TypedDict):
    outcome: ExtractionOutcome
    extraction_id: UUID | None
    provenance_edge_ids: list[UUID]


def _run_pass1(
    method: ExtractionMethod,
    data: bytes,
    *,
    content_type: str,
    content_type_conf: float,
) -> ExtractionOutcome:
    if method == "xlsx":
        return parse_xlsx(
            data,
            content_type=content_type,
            content_type_conf=content_type_conf,
        )
    if method == "csv":
        return parse_csv(
            data,
            content_type=content_type,
            content_type_conf=content_type_conf,
        )
    if method == "json":
        return parse_json(
            data,
            content_type=content_type,
            content_type_conf=content_type_conf,
        )
    if method in ("pdf_text", "pdf_table"):
        return parse_pdf(
            data,
            content_type=content_type,
            content_type_conf=content_type_conf,
        )
    return ExtractionOutcome(
        method=method,
        method_version="pending",
        derivation="extracted",
        confidence=1.0,
        status="failed",
        content_type=content_type,
        content_type_conf=content_type_conf,
        blocks=[],
    )


def extract_document(
    document: Document,
    data: bytes,
    *,
    min_confidence: float = DEFAULT_MAGIKA_MIN_CONFIDENCE,
    pass2: Pass2Fn | None = None,
) -> ExtractionOutcome:
    """Magika route → Pass 1 → optional Pass 2 only if Pass 1 has no blocks.

    Does not write to the DB. Use `extract_and_persist` for persistence.
    """
    decision = route_document_bytes(
        data=data,
        declared_format=document.format,
        min_confidence=min_confidence,
    )

    if decision["kind"] == "quarantine":
        return ExtractionOutcome(
            method=decision["method"] or "pdf_text",
            method_version="magika-router-1",
            derivation="ambiguous",
            confidence=min(decision["content_type_conf"], 0.999),
            status="quarantined",
            content_type=decision["content_type"],
            content_type_conf=decision["content_type_conf"],
            blocks=[],
        )

    if decision["kind"] == "unsupported":
        return ExtractionOutcome(
            method=decision["method"] or "pdf_text",
            method_version="magika-router-1",
            derivation="ambiguous",
            confidence=min(decision["content_type_conf"], 0.999),
            status="unsupported",
            content_type=decision["content_type"],
            content_type_conf=decision["content_type_conf"],
            blocks=[],
        )

    method = decision["method"]
    if method is None:
        return ExtractionOutcome(
            method="pdf_text",
            method_version="magika-router-1",
            derivation="ambiguous",
            confidence=min(decision["content_type_conf"], 0.999),
            status="failed",
            content_type=decision["content_type"],
            content_type_conf=decision["content_type_conf"],
            blocks=[],
        )

    pass1 = _run_pass1(
        method,
        data,
        content_type=decision["content_type"],
        content_type_conf=decision["content_type_conf"],
    )
    if pass1["blocks"]:
        return pass1

    if pass2 is not None:
        pass2_outcome = pass2(document, data, pass1)
        if pass2_outcome is not None:
            return pass2_outcome

    return pass1


def persist_outcome(
    connection: Connection,
    *,
    document_id: UUID,
    outcome: ExtractionOutcome,
) -> ExtractPersistResult:
    extraction = create_extraction(
        connection,
        ExtractionCreate(
            document_id=document_id,
            method=outcome["method"],
            method_version=outcome["method_version"],
            derivation=outcome["derivation"],
            confidence=outcome["confidence"],
            ok=outcome["status"] == "parsed",
            payload={"blocks": list(outcome["blocks"])},
            content_type=outcome["content_type"] or None,
            content_type_conf=outcome["content_type_conf"],
            status=outcome["status"],
        ),
    )

    edge_ids: list[UUID] = []
    for block in outcome["blocks"]:
        if block["page"] is None and block["region"] is None:
            continue
        edge = create_provenance_edge(
            connection,
            ProvenanceEdgeCreate(
                document_id=document_id,
                extraction_id=extraction.id,
                method=outcome["method"],
                derivation=outcome["derivation"],
                confidence=outcome["confidence"],
                page=block["page"],
                region=block["region"],
            ),
        )
        edge_ids.append(edge.id)

    return ExtractPersistResult(
        outcome=outcome,
        extraction_id=extraction.id,
        provenance_edge_ids=edge_ids,
    )


def extract_and_persist(
    connection: Connection,
    document: Document,
    data: bytes,
    *,
    min_confidence: float = DEFAULT_MAGIKA_MIN_CONFIDENCE,
    pass2: Pass2Fn | None = None,
) -> ExtractPersistResult:
    outcome = extract_document(
        document,
        data,
        min_confidence=min_confidence,
        pass2=pass2,
    )
    return persist_outcome(connection, document_id=document.id, outcome=outcome)
