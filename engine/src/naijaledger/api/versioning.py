"""API contract version header (spec 0024)."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

API_CONTRACT_VERSION = "1"


def build_api_version_middleware() -> type:
    """Return middleware that sets ``API-Version`` on ``/v1`` responses."""

    class ApiVersionMiddleware:
        def __init__(self, app: ASGIApp) -> None:
            self.app = app

        async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return

            path = scope.get("path", "")
            if not str(path).startswith("/v1"):
                await self.app(scope, receive, send)
                return

            async def send_with_version(message: Message) -> None:
                if message["type"] == "http.response.start":
                    headers = list(message.get("headers", []))
                    headers.append((b"api-version", API_CONTRACT_VERSION.encode("latin-1")))
                    message = {**message, "headers": headers}
                await send(message)

            await self.app(scope, receive, send_with_version)

    return ApiVersionMiddleware
