from collections.abc import Callable
from importlib.metadata import version
from typing import Any, Protocol

from naijaledger.extract.outcome import Block, ExtractionOutcome

OCR_METHOD_VERSION = f"tesseract-pytesseract-{version('pytesseract')}"
DEFAULT_OCR_MAX_PAGES = 20
DEFAULT_OCR_SCALE = 2.0
# Mean Tesseract word confidence is 0–100; map into (0, 1) for derivation=inferred.
_MAX_INFERRED_CONFIDENCE = 0.999


class _PilImage(Protocol):
    size: tuple[int, int]


class _PageBitmap(Protocol):
    def to_pil(self) -> _PilImage: ...


class _PdfPage(Protocol):
    def render(self, scale: float = ...) -> _PageBitmap: ...


class _PdfDocument(Protocol):
    def __len__(self) -> int: ...

    def __getitem__(self, index: int) -> _PdfPage: ...


PdfDocumentFactory = Callable[[bytes], _PdfDocument]
OcrImageFn = Callable[[_PilImage], tuple[str, float]]

_pdf_factory: PdfDocumentFactory | None = None
_ocr_image_fn: OcrImageFn | None = None


def configure_ocr_backends(
    *,
    pdf_factory: PdfDocumentFactory | None = None,
    ocr_image_fn: OcrImageFn | None = None,
) -> None:
    """Test hooks for PDF render + Tesseract."""
    global _pdf_factory, _ocr_image_fn
    _pdf_factory = pdf_factory
    _ocr_image_fn = ocr_image_fn


def _default_pdf_document(data: bytes) -> _PdfDocument:
    import pypdfium2 as pdfium

    return pdfium.PdfDocument(data)  # type: ignore[no-any-return]


def _default_ocr_image(image: _PilImage) -> tuple[str, float]:
    import pytesseract

    text = pytesseract.image_to_string(image)
    data: dict[str, Any] = pytesseract.image_to_data(
        image,
        output_type=pytesseract.Output.DICT,
    )
    confs: list[int] = []
    for raw in data.get("conf", []):
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value >= 0:
            confs.append(value)
    mean = (sum(confs) / len(confs) / 100.0) if confs else 0.5
    confidence = min(max(mean, 0.0), _MAX_INFERRED_CONFIDENCE)
    return text, confidence


def _get_pdf_document(data: bytes) -> _PdfDocument:
    factory = _pdf_factory or _default_pdf_document
    return factory(data)


def _ocr_image(image: _PilImage) -> tuple[str, float]:
    fn = _ocr_image_fn or _default_ocr_image
    return fn(image)


def ocr_pdf_bytes(
    data: bytes,
    *,
    content_type: str,
    content_type_conf: float,
    max_pages: int = DEFAULT_OCR_MAX_PAGES,
    scale: float = DEFAULT_OCR_SCALE,
) -> ExtractionOutcome:
    """Pass-2 OCR: render PDF pages and run Tesseract. Always `inferred`."""
    document = _get_pdf_document(data)
    page_count = min(len(document), max_pages)
    blocks: list[Block] = []
    confidences: list[float] = []

    for page_index in range(page_count):
        bitmap = document[page_index].render(scale=scale)
        image = bitmap.to_pil()
        text, page_confidence = _ocr_image(image)
        cleaned = text.strip()
        if not cleaned:
            continue
        confidences.append(page_confidence)
        blocks.append(
            Block(
                kind="text",
                payload={"text": cleaned, "ocr": True},
                page=page_index + 1,
                region=None,
            )
        )

    if confidences:
        confidence = min(sum(confidences) / len(confidences), _MAX_INFERRED_CONFIDENCE)
    else:
        confidence = 0.5

    return ExtractionOutcome(
        method="ocr",
        method_version=OCR_METHOD_VERSION,
        derivation="inferred",
        confidence=confidence,
        status="parsed" if blocks else "failed",
        content_type=content_type,
        content_type_conf=content_type_conf,
        blocks=blocks,
    )
