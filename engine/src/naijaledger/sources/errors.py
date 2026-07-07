class SourceError(Exception):
    """Base error for source registry operations."""


class SourceNotFoundError(SourceError):
    """Raised when a source id does not exist."""


class InvalidSourceTransitionError(SourceError):
    """Raised when a lifecycle transition is not allowed."""
