from collections.abc import Callable
from typing import Protocol

from naijaledger.extract.types import ContentTypeDetection


class _MagikaContentType(Protocol):
    label: str
    mime_type: str


class _MagikaResult(Protocol):
    score: float
    output: _MagikaContentType


class _MagikaClient(Protocol):
    def identify_bytes(self, content: bytes) -> _MagikaResult: ...


_magika_factory: Callable[[], _MagikaClient] | None = None
_magika_client: _MagikaClient | None = None


def _default_magika_factory() -> _MagikaClient:
    from magika import Magika

    return Magika()  # type: ignore[return-value]


def configure_magika_factory(factory: Callable[[], _MagikaClient] | None) -> None:
    """Test hook: inject a Magika factory; None restores the default."""
    global _magika_factory, _magika_client
    _magika_factory = factory
    _magika_client = None


def _get_magika() -> _MagikaClient:
    global _magika_client
    if _magika_client is None:
        factory = _magika_factory or _default_magika_factory
        _magika_client = factory()
    return _magika_client


def detect_content_type(data: bytes) -> ContentTypeDetection:
    result = _get_magika().identify_bytes(data)
    return ContentTypeDetection(
        label=result.output.label,
        mime_type=result.output.mime_type,
        confidence=float(result.score),
    )
