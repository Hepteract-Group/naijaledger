from typing import TypedDict


class ArchiveStoreResult(TypedDict):
    archive_key: str
    content_hash: str
    byte_count: int
    created: bool
