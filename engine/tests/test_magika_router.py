import io
import zipfile
from unittest.mock import MagicMock

import pytest
from sqlalchemy import text

from naijaledger.extract.detect import configure_magika_factory, detect_content_type
from naijaledger.extract.route import decide_extraction_route
from naijaledger.extract.router import record_quarantine, route_document_bytes
from naijaledger.extract.types import ContentTypeDetection
from naijaledger.extractions.service import list_extractions_for_document
from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import create_source


@pytest.fixture(autouse=True)
def _reset_magika_factory() -> None:
    configure_magika_factory(None)
    yield
    configure_magika_factory(None)


def _seed_document(db_connection, *, fmt: str = "pdf", sha: str = "magika-hash"):
    source = create_source(
        db_connection,
        SourceCreate(
            name="Magika Router Test",
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
    return db_connection.execute(
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


def _fake_magika(label: str, mime: str, score: float):
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


def test_decide_pass1_for_matching_pdf() -> None:
    decision = decide_extraction_route(
        detection=ContentTypeDetection(
            label="pdf",
            mime_type="application/pdf",
            confidence=0.99,
        ),
        declared_format="pdf",
    )
    assert decision["kind"] == "pass1"
    assert decision["method"] == "pdf_text"


def test_decide_quarantine_on_low_confidence() -> None:
    decision = decide_extraction_route(
        detection=ContentTypeDetection(
            label="pdf",
            mime_type="application/pdf",
            confidence=0.2,
        ),
        declared_format="pdf",
    )
    assert decision["kind"] == "quarantine"
    assert decision["reason"] == "low_confidence"


def test_decide_quarantine_on_format_mismatch() -> None:
    decision = decide_extraction_route(
        detection=ContentTypeDetection(
            label="html",
            mime_type="text/html",
            confidence=0.95,
        ),
        declared_format="json",
    )
    assert decision["kind"] == "quarantine"
    assert decision["reason"] is not None
    assert "format_mismatch" in decision["reason"]


def test_decide_unsupported_for_html_catalog() -> None:
    decision = decide_extraction_route(
        detection=ContentTypeDetection(
            label="html",
            mime_type="text/html",
            confidence=0.95,
        ),
        declared_format="html",
    )
    assert decision["kind"] == "unsupported"


def test_route_document_bytes_uses_injected_magika() -> None:
    configure_magika_factory(_fake_magika("xlsx", "application/vnd.ms-excel", 0.97))
    decision = route_document_bytes(data=b"unused", declared_format="xlsx")
    assert decision["kind"] == "pass1"
    assert decision["method"] == "xlsx"


def test_record_quarantine_writes_no_parsed_blocks(db_connection) -> None:
    document_id = _seed_document(db_connection, fmt="pdf", sha="quarantine-hash")
    configure_magika_factory(_fake_magika("html", "text/html", 0.98))
    decision = route_document_bytes(data=b"<html></html>", declared_format="pdf")
    assert decision["kind"] == "quarantine"

    extraction = record_quarantine(
        db_connection,
        document_id=document_id,
        decision=decision,
    )
    assert extraction.status == "quarantined"
    assert extraction.ok is False
    assert extraction.payload["blocks"] == []
    assert list_extractions_for_document(db_connection, document_id) == [extraction]


def test_detect_content_type_real_pdf_bytes() -> None:
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"
    detection = detect_content_type(pdf)
    assert detection["label"] == "pdf"
    assert detection["confidence"] > 0.5


def test_detect_content_type_real_xlsx_bytes() -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"></workbook>',
        )
    detection = detect_content_type(buf.getvalue())
    assert detection["label"] == "xlsx"
    assert detection["confidence"] > 0.5
