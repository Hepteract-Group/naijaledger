from datetime import UTC, datetime, timedelta

import httpx
import pytest

from naijaledger.seeds.catalog import SEED_ADDED_BY
from naijaledger.sources.health import (
    HealthProbeResult,
    content_fingerprint,
    derive_health_status,
    probe_source_url,
    run_health_monitor,
)
from naijaledger.sources.models import SourceCreate
from naijaledger.sources.service import approve_source, create_source, get_source


def _probe(
    *,
    http_status: int | None = 200,
    tls_not_after: datetime | None = None,
    content_fingerprint: str | None = "abc",
    error: str | None = None,
) -> HealthProbeResult:
    return HealthProbeResult(
        http_status=http_status,
        tls_not_after=tls_not_after,
        content_fingerprint=content_fingerprint,
        error=error,
    )


def test_content_fingerprint_is_stable() -> None:
    body = b"<html>open contracting</html>"
    assert content_fingerprint(body) == content_fingerprint(body)


def test_derive_health_status_tls_expired() -> None:
    now = datetime(2026, 7, 7, tzinfo=UTC)
    expired = now - timedelta(days=1)
    status, detail, drift = derive_health_status(
        _probe(tls_not_after=expired),
        previous_fingerprint=None,
        now=now,
        tls_warning_days=30,
    )
    assert status == "tls_expired"
    assert "expired" in detail
    assert drift is False


def test_derive_health_status_down_on_connection_error() -> None:
    now = datetime(2026, 7, 7, tzinfo=UTC)
    status, _, _ = derive_health_status(
        _probe(http_status=None, error="connection refused"),
        previous_fingerprint=None,
        now=now,
        tls_warning_days=30,
    )
    assert status == "down"


def test_derive_health_status_degraded_on_schema_drift() -> None:
    now = datetime(2026, 7, 7, tzinfo=UTC)
    status, detail, drift = derive_health_status(
        _probe(content_fingerprint="new-hash"),
        previous_fingerprint="old-hash",
        now=now,
        tls_warning_days=30,
    )
    assert status == "degraded"
    assert drift is True
    assert "drift" in detail


def test_derive_health_status_healthy() -> None:
    now = datetime(2026, 7, 7, tzinfo=UTC)
    future = now + timedelta(days=90)
    status, _, _ = derive_health_status(
        _probe(tls_not_after=future, content_fingerprint="same"),
        previous_fingerprint="same",
        now=now,
        tls_warning_days=30,
    )
    assert status == "healthy"


def test_run_health_monitor_updates_source(db_connection) -> None:
    created = create_source(
        db_connection,
        SourceCreate(
            name="Probe Test",
            jurisdiction="federal",
            category="procurement",
            url="https://example.com/health",
            fetch_method="http",
            format="html",
            added_by=SEED_ADDED_BY,
        ),
    )
    approve_source(db_connection, created.id, approved_by="test")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>stable</html>")

    client = httpx.Client(transport=httpx.MockTransport(handler))

    summary = run_health_monitor(db_connection, client=client, now=datetime(2026, 7, 7, tzinfo=UTC))
    updated = get_source(db_connection, created.id)

    assert summary["checked"] >= 1
    assert updated.health_status == "healthy"
    assert updated.schema_fingerprint is not None


def test_probe_source_url_rejects_localhost() -> None:
    client = httpx.Client()
    with pytest.raises(ValueError, match="blocked hostname"):
        probe_source_url("http://localhost/nope", client=client)
