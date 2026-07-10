"""OpenAPI / versioning / rate-limit tests (spec 0024 / E9.2)."""

from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy.engine import Connection

from naijaledger.api.app import create_app
from naijaledger.api.deps import get_connection
from naijaledger.api.rate_limit import client_key, create_fixed_window_limiter
from naijaledger.config import Settings


def _settings(**overrides: object) -> Settings:
    base = Settings(
        api_rate_limit_enabled=True,
        api_rate_limit_per_minute=5,
        api_trust_forwarded_for=False,
        api_cors_origins=["http://localhost:5174"],
    )
    return base.model_copy(update=overrides)


def test_openapi_describes_flags_as_hypotheses() -> None:
    client = TestClient(create_app(_settings(api_rate_limit_enabled=False)))
    spec = client.get("/openapi.json").json()
    description = spec["info"]["description"].lower()
    assert "hypothes" in description
    assert "not verified" in description or "verified claims" in description
    tag_names = {tag["name"] for tag in spec["tags"]}
    assert {"sources", "parties", "flags"} <= tag_names


def test_api_version_header_on_v1(
    db_connection: Connection,
) -> None:
    application = create_app(_settings(api_rate_limit_enabled=False))

    def _override() -> Generator[Connection, None, None]:
        yield db_connection

    application.dependency_overrides[get_connection] = _override
    client = TestClient(application)
    response = client.get("/v1/parties")
    assert response.status_code == 200
    assert response.headers.get("api-version") == "1"


def test_rate_limit_returns_429_with_retry_after(
    db_connection: Connection,
) -> None:
    application = create_app(_settings(api_rate_limit_per_minute=5))

    def _override() -> Generator[Connection, None, None]:
        yield db_connection

    application.dependency_overrides[get_connection] = _override
    client = TestClient(application)
    origin = {"Origin": "http://localhost:5174"}
    for _ in range(5):
        assert client.get("/v1/parties", headers=origin).status_code == 200
    limited = client.get("/v1/parties", headers=origin)
    assert limited.status_code == 429
    assert limited.headers.get("retry-after") is not None
    assert limited.headers.get("access-control-allow-origin") == "http://localhost:5174"
    assert client.get("/health").status_code == 200


def test_xff_does_not_bypass_when_untrusted(
    db_connection: Connection,
) -> None:
    application = create_app(_settings(api_rate_limit_per_minute=3, api_trust_forwarded_for=False))

    def _override() -> Generator[Connection, None, None]:
        yield db_connection

    application.dependency_overrides[get_connection] = _override
    client = TestClient(application)
    for i in range(3):
        assert (
            client.get("/v1/parties", headers={"X-Forwarded-For": f"203.0.113.{i}"}).status_code
            == 200
        )
    assert client.get("/v1/parties", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 429


def test_cors_credentials_disabled() -> None:
    application = create_app(_settings(api_rate_limit_enabled=False))
    cors = [
        m
        for m in application.user_middleware
        if getattr(m.cls, "__name__", "") == "CORSMiddleware" or "CORSMiddleware" in str(m.cls)
    ]
    assert cors
    # Starlette stores kwargs on the middleware entry.
    assert cors[0].kwargs.get("allow_credentials") is False


def test_fixed_window_limiter_unit() -> None:
    take = create_fixed_window_limiter(limit=2, window_seconds=60, max_keys=10)
    assert take("a", now=0.0) == (True, 0)
    assert take("a", now=1.0) == (True, 0)
    allowed, retry = take("a", now=2.0)
    assert allowed is False
    assert retry >= 1
    assert take("a", now=60.0)[0] is True


def test_client_key_ignores_xff_by_default() -> None:
    from starlette.requests import Request

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "path": "/v1/parties",
        "raw_path": b"/v1/parties",
        "root_path": "",
        "scheme": "http",
        "query_string": b"",
        "headers": [(b"x-forwarded-for", b"203.0.113.9")],
        "client": ("127.0.0.1", 12345),
        "server": ("test", 80),
    }
    request = Request(scope)
    assert client_key(request, trust_forwarded_for=False) == "127.0.0.1"
    assert client_key(request, trust_forwarded_for=True) == "203.0.113.9"
