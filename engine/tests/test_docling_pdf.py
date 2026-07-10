from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from naijaledger.documents.models import Document
from naijaledger.extract.detect import configure_magika_factory
from naijaledger.extract.docling_map import blocks_from_docling_dict
from naijaledger.extract.parsers_pdf import (
    DOCLING_METHOD_VERSION,
    configure_docling_converter_factory,
    parse_pdf,
)
from naijaledger.extract.pipeline import extract_document


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


def _document() -> Document:
    now = datetime.now(tz=UTC)
    return Document(
        id=uuid4(),
        source_id=uuid4(),
        first_fetch_id=uuid4(),
        sha256="pdfhash",
        format="pdf",
        archive_key="sha256/pdfhash",
        title=None,
        published_at=None,
        meta=None,
        created_at=now,
        updated_at=now,
    )


_DOCLING_FIXTURE = {
    "tables": [
        {
            "label": "table",
            "prov": [
                {
                    "page_no": 1,
                    "bbox": {"l": 10.0, "t": 200.0, "r": 300.0, "b": 100.0},
                }
            ],
            "data": {
                "grid": [
                    [{"text": "Agency"}, {"text": "Amount"}],
                    [{"text": "BPP"}, {"text": "1000"}],
                ]
            },
        }
    ],
    "texts": [
        {
            "text": "Award register",
            "label": "section_header",
            "prov": [
                {
                    "page_no": 1,
                    "bbox": {"l": 10.0, "t": 250.0, "r": 120.0, "b": 230.0},
                }
            ],
        }
    ],
}


def test_blocks_from_docling_dict_tables_and_text() -> None:
    blocks = blocks_from_docling_dict(_DOCLING_FIXTURE)
    assert len(blocks) == 2
    table = blocks[0]
    assert table["kind"] == "table"
    assert table["page"] == 1
    assert table["region"] == {"x0": 10.0, "y0": 100.0, "x1": 300.0, "y1": 200.0}
    assert table["payload"]["rows"][0] == ["Agency", "Amount"]
    assert blocks[1]["kind"] == "text"
    assert blocks[1]["payload"]["text"] == "Award register"


def test_parse_pdf_uses_docling_and_sets_method_version() -> None:
    document = MagicMock()
    document.export_to_dict.return_value = _DOCLING_FIXTURE
    conversion = MagicMock()
    conversion.document = document
    converter = MagicMock()
    converter.convert.return_value = conversion
    configure_docling_converter_factory(lambda: converter)
    try:
        outcome = parse_pdf(
            b"%PDF-1.4 fake",
            content_type="application/pdf",
            content_type_conf=0.98,
        )
        assert outcome["derivation"] == "extracted"
        assert outcome["confidence"] == 1.0
        assert outcome["method"] == "pdf_table"
        assert outcome["method_version"] == DOCLING_METHOD_VERSION
        assert outcome["blocks"][0]["kind"] == "table"
        assert outcome["blocks"][0]["page"] == 1
        assert outcome["blocks"][0]["region"] is not None
        converter.convert.assert_called_once()
    finally:
        configure_docling_converter_factory(None)


def test_extract_document_routes_pdf_to_docling() -> None:
    document = MagicMock()
    document.export_to_dict.return_value = _DOCLING_FIXTURE
    conversion = MagicMock()
    conversion.document = document
    converter = MagicMock()
    converter.convert.return_value = conversion
    configure_magika_factory(_fake_magika("pdf", "application/pdf"))
    configure_docling_converter_factory(lambda: converter)
    try:
        outcome = extract_document(_document(), b"%PDF-1.4 fake")
        assert outcome["status"] == "parsed"
        assert outcome["method"] == "pdf_table"
        assert any(block["kind"] == "table" for block in outcome["blocks"])
    finally:
        configure_magika_factory(None)
        configure_docling_converter_factory(None)
