from datetime import timedelta
from typing import Literal

Jurisdiction = Literal["federal", "state", "lga"]
SourceCategory = Literal["budget", "procurement", "payments", "company", "election", "other"]
FetchMethod = Literal["http", "scrapling", "playwright", "api", "manual"]
SourceFormat = Literal["pdf", "xlsx", "csv", "json", "html", "image"]
HealthStatus = Literal["healthy", "degraded", "down", "tls_expired", "unknown"]
SourceStatus = Literal["proposed", "approved", "retired"]
IngestRole = Literal["leaf", "catalog", "discovery_ui", "search_ui"]

Cadence = timedelta
