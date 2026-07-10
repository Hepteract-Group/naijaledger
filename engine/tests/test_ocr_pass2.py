import io
from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from PIL import Image, ImageDraw

from naijaledger.documents.models import Document
from naijaledger.extract.detect import configure_magika_factory
from naijaledger.extract.outcome import ExtractionOutcome
from naijaledger.extract.parsers_ocr import configure_ocr_backends, ocr_pdf_bytes
from naijaledger.extract.parsers_pdf import configure_docling_converter_factory
from naijaledger.extract.pipeline import extract_document


def _scanned_pdf_bytes(text: str = "Award Amount 1000") -> bytes:
    image = Image.new("RGB", (400, 120), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 50), text, fill="black")
    buf = io.BytesIO()
    image.save(buf, format="PDF")
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


def _empty_docling_factory():
    document = MagicMock()
    document.export_to_dict.return_value = {"tables": [], "texts": []}
    conversion = MagicMock()
    conversion.document = document
    converter = MagicMock()
    converter.convert.return_value = conversion
    return lambda: converter


def _document() -> Document:
    now = datetime.now(tz=UTC)
    return Document(
        id=uuid4(),
        source_id=uuid4(),
        first_fetch_id=uuid4(),
        sha256="scanhash",
        format="pdf",
        archive_key="sha256/scanhash",
        title=None,
        published_at=None,
        meta=None,
        created_at=now,
        updated_at=now,
    )


def test_ocr_pdf_bytes_inferred() -> None:
    configure_ocr_backends(ocr_image_fn=lambda _img: ("Award Amount 1000", 0.9))
    try:
        # Still need a PDF document length — use real pypdfium for page count.
        configure_ocr_backends(
            pdf_factory=None,
            ocr_image_fn=lambda _img: ("Award Amount 1000", 0.9),
        )
        outcome = ocr_pdf_bytes(
            _scanned_pdf_bytes(),
            content_type="application/pdf",
            content_type_conf=0.95,
        )
        assert outcome["derivation"] == "inferred"
        assert outcome["confidence"] < 1.0
        assert outcome["method"] == "ocr"
        assert outcome["blocks"]
        assert "Award Amount 1000" in outcome["blocks"][0]["payload"]["text"]
        assert outcome["blocks"][0]["page"] == 1
    finally:
        configure_ocr_backends()


def test_scanned_pdf_routes_to_pass2_inferred() -> None:
    configure_magika_factory(_fake_magika("pdf", "application/pdf"))
    configure_docling_converter_factory(_empty_docling_factory())
    configure_ocr_backends(ocr_image_fn=lambda _img: ("Award Amount 1000", 0.85))
    try:
        outcome = extract_document(_document(), _scanned_pdf_bytes())
        assert outcome["derivation"] == "inferred"
        assert outcome["method"] == "ocr"
        assert outcome["confidence"] < 1.0
        assert outcome["status"] == "parsed"
        assert outcome["blocks"][0]["payload"]["text"] == "Award Amount 1000"
    finally:
        configure_magika_factory(None)
        configure_docling_converter_factory(None)
        configure_ocr_backends()


def test_pass2_skipped_when_disabled() -> None:
    configure_magika_factory(_fake_magika("pdf", "application/pdf"))
    configure_docling_converter_factory(_empty_docling_factory())
    called = {"value": False}

    def pass2(_doc: Document, _data: bytes, _pass1: ExtractionOutcome):
        called["value"] = True
        return None

    try:
        outcome = extract_document(
            _document(),
            _scanned_pdf_bytes(),
            pass2=pass2,
            enable_pass2=False,
        )
        assert called["value"] is False
        assert outcome["blocks"] == []
        assert outcome["status"] == "failed"
    finally:
        configure_magika_factory(None)
        configure_docling_converter_factory(None)


def test_real_tesseract_on_scanned_pdf() -> None:
    configure_ocr_backends()
    outcome = ocr_pdf_bytes(
        _scanned_pdf_bytes("Hello NaijaLedger"),
        content_type="application/pdf",
        content_type_conf=0.9,
    )
    assert outcome["derivation"] == "inferred"
    assert outcome["confidence"] < 1.0
    assert "NaijaLedger" in outcome["blocks"][0]["payload"]["text"]
