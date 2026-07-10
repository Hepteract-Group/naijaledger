from typing import Literal

ExtractionMethod = Literal[
    "xlsx",
    "csv",
    "json",
    "pdf_text",
    "pdf_table",
    "ocr",
    "vision_llm",
]
ExtractionDerivation = Literal["extracted", "inferred", "ambiguous"]
ExtractionStatus = Literal["parsed", "quarantined", "unsupported", "failed"]

DETERMINISTIC_CONFIDENCE = 1.0
