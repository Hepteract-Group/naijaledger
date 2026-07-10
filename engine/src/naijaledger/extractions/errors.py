from naijaledger.extractions.types import ExtractionDerivation


class ExtractionValidationError(ValueError):
    """Raised when derivation/confidence rules are violated."""


def validate_derivation_confidence(
    derivation: ExtractionDerivation,
    confidence: float,
) -> None:
    if confidence < 0.0 or confidence > 1.0:
        msg = f"confidence must be in [0, 1], got {confidence}"
        raise ExtractionValidationError(msg)
    if derivation == "extracted" and confidence != 1.0:
        msg = "derivation=extracted requires confidence=1.0"
        raise ExtractionValidationError(msg)
    if derivation in ("inferred", "ambiguous") and confidence >= 1.0:
        msg = f"derivation={derivation} requires confidence < 1.0"
        raise ExtractionValidationError(msg)
