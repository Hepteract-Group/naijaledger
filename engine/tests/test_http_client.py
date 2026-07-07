import httpx

from naijaledger.http.client import create_http_client


def test_create_http_client_returns_configured_client() -> None:
    client = create_http_client()
    try:
        assert isinstance(client, httpx.Client)
    finally:
        client.close()
