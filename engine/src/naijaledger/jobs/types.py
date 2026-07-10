from typing import Literal

JobKind = Literal["fetch_source"]
JobStatus = Literal["queued", "running", "succeeded", "failed", "dead"]

DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_LOCK_TIMEOUT_SECONDS = 1800
BACKOFF_SECONDS = (60, 300, 900)
