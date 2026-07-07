import hashlib
import logging
import socket
import ssl
from datetime import UTC, datetime
from typing import TypedDict
from urllib.parse import urlparse
from uuid import UUID

import httpx
from sqlalchemy.engine import Connection

from naijaledger.sources.models import SourceRecord, SourceUpdate
from naijaledger.sources.service import list_sources, update_source
from naijaledger.sources.types import HealthStatus

logger = logging.getLogger("naijaledger.health")

_BLOCKED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0", "::1"})
_MAX_FINGERPRINT_BYTES = 1_048_576


class HealthProbeResult(TypedDict):
    http_status: int | None
    tls_not_after: datetime | None
    content_fingerprint: str | None
    error: str | None


class HealthCheckOutcome(TypedDict):
    source_id: UUID
    source_name: str
    url: str
    previous_status: HealthStatus
    health_status: HealthStatus
    detail: str
    schema_drift: bool


class HealthMonitorSummary(TypedDict):
    checked: int
    healthy: int
    degraded: int
    down: int
    tls_expired: int
    alerts: int


def content_fingerprint(body: bytes) -> str:
    return hashlib.sha256(body[:_MAX_FINGERPRINT_BYTES]).hexdigest()


def _is_blocked_hostname(hostname: str) -> bool:
    normalized = hostname.lower().rstrip(".")
    if normalized in _BLOCKED_HOSTS:
        return True
    return normalized.endswith(".localhost")


def validate_probe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        msg = f"unsupported URL scheme for health probe: {parsed.scheme}"
        raise ValueError(msg)
    hostname = parsed.hostname
    if not hostname:
        msg = "URL hostname is required for health probe"
        raise ValueError(msg)
    if _is_blocked_hostname(hostname):
        msg = f"blocked hostname for health probe: {hostname}"
        raise ValueError(msg)


def fetch_tls_not_after(
    hostname: str,
    *,
    port: int = 443,
    timeout: float = 10.0,
) -> datetime | None:
    context = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=timeout) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as tls_sock:
                cert = tls_sock.getpeercert()
    except OSError:
        return None

    if cert is None:
        return None
    not_after_raw = cert.get("notAfter")
    if not isinstance(not_after_raw, str):
        return None
    return datetime.strptime(not_after_raw, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=UTC)


def probe_source_url(
    url: str,
    *,
    client: httpx.Client,
) -> HealthProbeResult:
    validate_probe_url(url)
    parsed = urlparse(url)
    tls_not_after: datetime | None = None
    if parsed.scheme == "https" and parsed.hostname:
        tls_not_after = fetch_tls_not_after(parsed.hostname, port=parsed.port or 443)

    try:
        response = client.get(url, follow_redirects=True)
    except httpx.HTTPError as exc:
        return HealthProbeResult(
            http_status=None,
            tls_not_after=tls_not_after,
            content_fingerprint=None,
            error=str(exc),
        )

    body = response.content
    fingerprint = content_fingerprint(body) if body else None
    return HealthProbeResult(
        http_status=response.status_code,
        tls_not_after=tls_not_after,
        content_fingerprint=fingerprint,
        error=None,
    )


def derive_health_status(
    probe: HealthProbeResult,
    *,
    previous_fingerprint: str | None,
    now: datetime,
    tls_warning_days: int,
) -> tuple[HealthStatus, str, bool]:
    if probe["tls_not_after"] is not None and probe["tls_not_after"] <= now:
        return "tls_expired", "TLS certificate has expired", False

    if probe["error"] is not None:
        return "down", probe["error"], False

    status_code = probe["http_status"]
    if status_code is None:
        return "down", "no HTTP status returned", False
    if status_code >= 500:
        return "down", f"HTTP {status_code}", False

    schema_drift = False
    if (
        previous_fingerprint is not None
        and probe["content_fingerprint"] is not None
        and probe["content_fingerprint"] != previous_fingerprint
    ):
        schema_drift = True

    if status_code >= 400:
        return "degraded", f"HTTP {status_code}", schema_drift

    if probe["tls_not_after"] is not None:
        days_left = (probe["tls_not_after"] - now).days
        if days_left <= tls_warning_days:
            return "degraded", f"TLS certificate expires in {days_left} days", schema_drift

    if schema_drift:
        return "degraded", "schema/content fingerprint drift detected", True

    return "healthy", "reachable", schema_drift


def emit_health_alert(outcome: HealthCheckOutcome) -> None:
    if outcome["health_status"] == "healthy":
        logger.info(
            "source healthy: %s (%s)",
            outcome["source_name"],
            outcome["url"],
        )
        return

    logger.warning(
        "SOURCE HEALTH ALERT [%s] %s (%s): %s",
        outcome["health_status"].upper(),
        outcome["source_name"],
        outcome["url"],
        outcome["detail"],
    )


def check_source_health(
    connection: Connection,
    source: SourceRecord,
    *,
    client: httpx.Client,
    now: datetime,
    tls_warning_days: int,
) -> HealthCheckOutcome:
    probe = probe_source_url(source.url, client=client)
    health_status, detail, schema_drift = derive_health_status(
        probe,
        previous_fingerprint=source.schema_fingerprint,
        now=now,
        tls_warning_days=tls_warning_days,
    )

    fingerprint = probe["content_fingerprint"]
    if source.schema_fingerprint is None and fingerprint is not None:
        update_source(
            connection,
            source.id,
            SourceUpdate(health_status=health_status, schema_fingerprint=fingerprint),
        )
    else:
        update_source(connection, source.id, SourceUpdate(health_status=health_status))

    return HealthCheckOutcome(
        source_id=source.id,
        source_name=source.name,
        url=source.url,
        previous_status=source.health_status,
        health_status=health_status,
        detail=detail,
        schema_drift=schema_drift,
    )


def run_health_monitor(
    connection: Connection,
    *,
    client: httpx.Client | None = None,
    now: datetime | None = None,
    tls_warning_days: int = 30,
) -> HealthMonitorSummary:
    checked_at = now or datetime.now(tz=UTC)
    owned_client = client is None
    http_client = client or httpx.Client(timeout=20.0)

    summary: HealthMonitorSummary = {
        "checked": 0,
        "healthy": 0,
        "degraded": 0,
        "down": 0,
        "tls_expired": 0,
        "alerts": 0,
    }

    try:
        sources = list_sources(connection, status="approved")
        for source in sources:
            outcome = check_source_health(
                connection,
                source,
                client=http_client,
                now=checked_at,
                tls_warning_days=tls_warning_days,
            )
            summary["checked"] += 1
            if outcome["health_status"] == "healthy":
                summary["healthy"] += 1
            elif outcome["health_status"] == "degraded":
                summary["degraded"] += 1
            elif outcome["health_status"] == "down":
                summary["down"] += 1
            elif outcome["health_status"] == "tls_expired":
                summary["tls_expired"] += 1
            if outcome["health_status"] != "healthy":
                summary["alerts"] += 1
            emit_health_alert(outcome)
    finally:
        if owned_client:
            http_client.close()

    return summary
