from collections.abc import Callable
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Protocol

from naijaledger.extract.docling_map import blocks_from_docling_dict
from naijaledger.extract.outcome import ExtractionOutcome
from naijaledger.extractions.types import DETERMINISTIC_CONFIDENCE

DOCLING_METHOD_VERSION = f"docling-{version('docling')}"


class _DoclingDocument(Protocol):
    def export_to_dict(self) -> dict[str, Any]: ...


class _ConversionResult(Protocol):
    document: _DoclingDocument


class _DocumentConverter(Protocol):
    def convert(self, source: str) -> _ConversionResult: ...


ConverterFactory = Callable[[], _DocumentConverter]

_converter_factory: ConverterFactory | None = None


def configure_docling_converter_factory(factory: ConverterFactory | None) -> None:
    global _converter_factory
    _converter_factory = factory


def _default_converter() -> _DocumentConverter:
    from docling.document_converter import DocumentConverter

    return DocumentConverter()  # type: ignore[return-value]


def _get_converter() -> _DocumentConverter:
    factory = _converter_factory or _default_converter
    return factory()


def parse_pdf(
    data: bytes,
    *,
    content_type: str,
    content_type_conf: float,
) -> ExtractionOutcome:
    with TemporaryDirectory(prefix="naijaledger-docling-") as tmp:
        pdf_path = Path(tmp) / "document.pdf"
        pdf_path.write_bytes(data)
        result = _get_converter().convert(str(pdf_path))
        document_dict = result.document.export_to_dict()

    blocks = blocks_from_docling_dict(document_dict)
    has_table = any(block["kind"] == "table" for block in blocks)

    return ExtractionOutcome(
        method="pdf_table" if has_table else "pdf_text",
        method_version=DOCLING_METHOD_VERSION,
        derivation="extracted",
        confidence=DETERMINISTIC_CONFIDENCE,
        status="parsed" if blocks else "failed",
        content_type=content_type,
        content_type_conf=content_type_conf,
        blocks=blocks,
    )
