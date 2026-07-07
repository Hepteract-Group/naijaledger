import ssl

import httpx
import truststore

from naijaledger.config import Settings, load_settings


def create_http_client(
    settings: Settings | None = None,
    *,
    timeout: float | None = None,
) -> httpx.Client:
    config = settings or load_settings()
    ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return httpx.Client(
        timeout=timeout if timeout is not None else config.fetch_http_timeout,
        verify=ssl_context,
    )
