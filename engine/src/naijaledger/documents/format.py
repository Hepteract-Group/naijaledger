from urllib.parse import urlparse

from naijaledger.sources.types import SourceFormat

_CONTENT_TYPE_FORMAT: dict[str, SourceFormat] = {
    "text/html": "html",
    "application/xhtml+xml": "html",
    "application/pdf": "pdf",
    "application/json": "json",
    "text/csv": "csv",
    "application/vnd.ms-excel": "xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "image/jpeg": "image",
    "image/png": "image",
    "image/webp": "image",
    "image/gif": "image",
}

_EXTENSION_FORMAT: dict[str, SourceFormat] = {
    ".html": "html",
    ".htm": "html",
    ".pdf": "pdf",
    ".json": "json",
    ".csv": "csv",
    ".xlsx": "xlsx",
    ".xls": "xlsx",
    ".jpg": "image",
    ".jpeg": "image",
    ".png": "image",
    ".webp": "image",
    ".gif": "image",
}


def _normalize_content_type(content_type: str | None) -> str | None:
    if content_type is None:
        return None
    stripped = content_type.split(";", 1)[0].strip().lower()
    return stripped or None


def _format_from_url(url: str) -> SourceFormat | None:
    path = urlparse(url).path.lower()
    for extension, document_format in _EXTENSION_FORMAT.items():
        if path.endswith(extension):
            return document_format
    return None


def infer_document_format(
    *,
    url: str,
    content_type: str | None,
    source_format: SourceFormat,
) -> SourceFormat:
    normalized = _normalize_content_type(content_type)
    if normalized is not None:
        mapped = _CONTENT_TYPE_FORMAT.get(normalized)
        if mapped is not None:
            return mapped
        if normalized.startswith("image/"):
            return "image"

    from_url = _format_from_url(url)
    if from_url is not None:
        return from_url

    return source_format
