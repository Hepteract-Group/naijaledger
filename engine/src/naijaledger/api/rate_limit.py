"""Fixed-window in-process rate limiter (spec 0024)."""

from __future__ import annotations

import time
from collections.abc import Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

EXEMPT_EXACT = frozenset({"/health", "/openapi.json", "/docs", "/redoc"})
EXEMPT_PREFIXES = ("/docs/", "/redoc/")


def client_key(request: Request, *, trust_forwarded_for: bool) -> str:
    if trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            leftmost = forwarded.split(",")[0].strip()
            if leftmost:
                return leftmost
    if request.client is not None and request.client.host:
        return request.client.host
    return "unknown"


def create_fixed_window_limiter(
    *,
    limit: int,
    window_seconds: int = 60,
    max_keys: int = 10_000,
) -> Callable[..., tuple[bool, int]]:
    """Return ``take(key, now=None) -> (allowed, retry_after_seconds)``."""

    windows: dict[str, tuple[int, float]] = {}

    def _prune(now: float) -> None:
        expired = [key for key, (_, start) in windows.items() if now - start >= window_seconds]
        for key in expired:
            del windows[key]
        while len(windows) > max_keys:
            oldest_key = min(windows.items(), key=lambda item: item[1][1])[0]
            del windows[oldest_key]

    def take(key: str, now: float | None = None) -> tuple[bool, int]:
        current = time.monotonic() if now is None else now
        _prune(current)
        entry = windows.get(key)
        if entry is None or current - entry[1] >= window_seconds:
            windows[key] = (1, current)
            return True, 0
        count, start = entry
        if count >= limit:
            retry_after = max(1, int(window_seconds - (current - start)) + 1)
            return False, retry_after
        windows[key] = (count + 1, start)
        return True, 0

    return take


def is_v1_path(path: str) -> bool:
    return path == "/v1" or path.startswith("/v1/")


def is_rate_limit_exempt(path: str) -> bool:
    if path in EXEMPT_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES)


def build_rate_limit_middleware(
    *,
    enabled: bool,
    limit: int,
    max_keys: int,
    trust_forwarded_for: bool,
) -> type:
    """Return a Starlette middleware class configured for ``app.add_middleware``."""

    take = create_fixed_window_limiter(limit=max(1, limit), max_keys=max(1, max_keys))

    class RateLimitMiddleware:
        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http" or not enabled:
                await self.app(scope, receive, send)
                return

            request = Request(scope, receive=receive)
            path = request.url.path
            if is_rate_limit_exempt(path) or not is_v1_path(path):
                await self.app(scope, receive, send)
                return

            key = client_key(request, trust_forwarded_for=trust_forwarded_for)
            allowed, retry_after = take(key)
            if not allowed:
                response: Response = JSONResponse(
                    {"detail": "rate limit exceeded"},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )
                await response(scope, receive, send)
                return

            await self.app(scope, receive, send)

    return RateLimitMiddleware
