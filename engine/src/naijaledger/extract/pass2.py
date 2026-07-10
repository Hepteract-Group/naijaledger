from naijaledger.documents.models import Document
from naijaledger.extract.outcome import ExtractionOutcome
from naijaledger.extract.parsers_ocr import DEFAULT_OCR_MAX_PAGES, ocr_pdf_bytes

# Vision-LLM is intentionally a no-op unless explicitly enabled later with a budget.
_VISION_LLM_ENABLED_DEFAULT = False


def default_pass2(
    document: Document,
    data: bytes,
    pass1: ExtractionOutcome,
    *,
    ocr_max_pages: int = DEFAULT_OCR_MAX_PAGES,
    vision_llm_enabled: bool = _VISION_LLM_ENABLED_DEFAULT,
) -> ExtractionOutcome | None:
    """Run when Pass 1 produced no blocks. OCR first; vision-LLM only if enabled + still empty."""
    if pass1["blocks"]:
        return None

    if document.format not in ("pdf", "image"):
        return None

    ocr_outcome = ocr_pdf_bytes(
        data,
        content_type=pass1["content_type"] or "application/pdf",
        content_type_conf=pass1["content_type_conf"],
        max_pages=ocr_max_pages,
    )
    if ocr_outcome["blocks"]:
        return ocr_outcome

    if vision_llm_enabled:
        # Cost-gated hook — no remote call until a budgeted client is wired (#31 follow-up).
        return ExtractionOutcome(
            method="vision_llm",
            method_version="vision-llm-disabled",
            derivation="inferred",
            confidence=0.5,
            status="failed",
            content_type=pass1["content_type"],
            content_type_conf=pass1["content_type_conf"],
            blocks=[],
        )

    return ocr_outcome
