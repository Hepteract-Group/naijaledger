import io
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from openpyxl import Workbook
from sqlalchemy import text

from naijaledger.documents.models import Document
from naijaledger.documents.service import get_document
from naijaledger.extract.detect import configure_magika_factory
from naijaledger.extract.outcome import Block, ExtractionOutcome
from naijaledger.extract.parsers_csv import parse_csv
from naijaledger.extract.parsers_json import parse_json
from naijaledger.extract.parsers_xlsx import parse_xlsx
from naijaledger.extract.pipeline import (
    extract_and_persist,
    extract_document,
    persist_outcome,
)
from naijaledger.extractions.service import (
    get_extraction,
    list_provenance_edges_for_extraction,
)
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import create_source


def _xlsx_bytes(rows: list[list[object]]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)
    buf = io.BytesIO()
    workbook.save(buf)
    return buf.getvalue()


def _fake_magika(label: str, mime: str, score: float = 0.99):
    def factory() -> MagicMock:
        client = MagicMock()
        output = MagicMock()
        output.label = label
        output.mime_type = mime
        result = MagicMock()
        result.output = output
        result.score = score
        client.identify_bytes.return_value = result
        return client

    return factory


def _document(*, fmt: str = "xlsx") -> Document:
    now = datetime.now(tz=UTC)
    return Document(
        id=uuid4(),
        source_id=uuid4(),
        first_fetch_id=uuid4(),
        sha256="deadbeef",
        format=fmt,  # type: ignore[arg-type]
        archive_key="sha256/deadbeef",
        title=None,
        published_at=None,
        meta=None,
        created_at=now,
        updated_at=now,
    )


def _seed_document(db_connection, *, fmt: str, sha: str) -> Document:
    source = create_source(
        db_connection,
        SourceCreate(
            name="Parser Orchestrator Test",
            jurisdiction="federal",
            category="procurement",
            url=f"https://example.com/file.{fmt}",
            fetch_method="http",
            format=fmt,  # type: ignore[arg-type]
            added_by=SEED_ADDED_BY,
        ),
    )
    fetch_id = db_connection.execute(
        text(
            """
            INSERT INTO fetch_records (
                source_id, url, requested_at, status_code, ok, sha256, archive_key
            ) VALUES (
                :source_id, :url, now(), 200, true, :sha, :archive_key
            )
            RETURNING id
            """
        ),
        {
            "source_id": source.id,
            "url": source.url,
            "sha": sha,
            "archive_key": f"sha256/{sha}",
        },
    ).scalar_one()
    document_id = db_connection.execute(
        text(
            """
            INSERT INTO documents (
                source_id, first_fetch_id, sha256, format, archive_key
            ) VALUES (
                :source_id, :fetch_id, :sha, :fmt, :archive_key
            )
            RETURNING id
            """
        ),
        {
            "source_id": source.id,
            "fetch_id": fetch_id,
            "sha": sha,
            "fmt": fmt,
            "archive_key": f"sha256/{sha}",
        },
    ).scalar_one()
    return get_document(db_connection, document_id)


def test_parse_xlsx_extracted() -> None:
    data = _xlsx_bytes([["agency", "amount"], ["BPP", 1000]])
    outcome = parse_xlsx(
        data,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        content_type_conf=0.99,
    )
    assert outcome["derivation"] == "extracted"
    assert outcome["confidence"] == 1.0
    assert outcome["status"] == "parsed"
    assert outcome["method"] == "xlsx"
    assert len(outcome["blocks"]) == 1
    assert outcome["blocks"][0]["payload"]["rows"][0] == ["agency", "amount"]


def test_parse_json_extracted() -> None:
    data = b'[{"ocid": "ocds-1", "value": 10}]'
    outcome = parse_json(data, content_type="application/json", content_type_conf=0.95)
    assert outcome["derivation"] == "extracted"
    assert outcome["confidence"] == 1.0
    assert outcome["method"] == "json"
    assert outcome["blocks"][0]["kind"] == "record"
    assert outcome["blocks"][0]["payload"]["value"]["ocid"] == "ocds-1"


def test_parse_csv_extracted() -> None:
    data = b"name,value\nLagos,1\n"
    outcome = parse_csv(data, content_type="text/csv", content_type_conf=0.9)
    assert outcome["derivation"] == "extracted"
    assert outcome["blocks"][0]["payload"]["rows"][1] == ["Lagos", "1"]


def test_extract_document_xlsx_via_router() -> None:
    configure_magika_factory(
        _fake_magika(
            "xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    )
    try:
        data = _xlsx_bytes([["a", "b"], [1, 2]])
        outcome = extract_document(_document(fmt="xlsx"), data)
        assert outcome["status"] == "parsed"
        assert outcome["method"] == "xlsx"
        assert outcome["blocks"]
    finally:
        configure_magika_factory(None)


def test_pass2_not_called_when_pass1_has_blocks() -> None:
    configure_magika_factory(_fake_magika("json", "application/json"))
    called = {"value": False}

    def pass2(_document: Document, _data: bytes, _pass1: ExtractionOutcome):
        called["value"] = True
        return None

    try:
        outcome = extract_document(
            _document(fmt="json"),
            b'{"ok": true}',
            pass2=pass2,
        )
        assert outcome["blocks"]
        assert called["value"] is False
    finally:
        configure_magika_factory(None)


def test_extract_and_persist_json(db_connection) -> None:
    configure_magika_factory(_fake_magika("json", "application/json"))
    try:
        document = _seed_document(db_connection, fmt="json", sha="json-orch-1")
        result = extract_and_persist(db_connection, document, b'[{"id": 1}]')
        assert result["extraction_id"] is not None
        extraction = get_extraction(db_connection, result["extraction_id"])
        assert extraction.derivation == "extracted"
        assert float(extraction.confidence) == 1.0
        assert extraction.status == "parsed"
    finally:
        configure_magika_factory(None)


def test_persist_writes_provenance_for_region_blocks(db_connection) -> None:
    document = _seed_document(db_connection, fmt="json", sha="json-orch-2")
    outcome = ExtractionOutcome(
        method="json",
        method_version="test-1",
        derivation="extracted",
        confidence=1.0,
        status="parsed",
        content_type="application/json",
        content_type_conf=0.9,
        blocks=[
            Block(
                kind="record",
                payload={"value": {"x": 1}},
                page=1,
                region={"x0": 0.0, "y0": 0.0, "x1": 10.0, "y1": 10.0},
            )
        ],
    )
    result = persist_outcome(db_connection, document_id=document.id, outcome=outcome)
    assert result["extraction_id"] is not None
    edges = list_provenance_edges_for_extraction(db_connection, result["extraction_id"])
    assert len(edges) == 1
    assert edges[0].page == 1


def test_real_magika_xlsx_roundtrip() -> None:
    configure_magika_factory(None)
    data = _xlsx_bytes([["col"], ["val"]])
    outcome = extract_document(_document(fmt="xlsx"), data)
    assert outcome["status"] == "parsed"
    assert outcome["method"] == "xlsx"
