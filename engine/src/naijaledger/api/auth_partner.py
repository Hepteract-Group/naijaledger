"""Partner bearer-token auth for export routes (spec 0025)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request


def token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]


def extract_bearer(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def verify_partner_token(token: str, configured: list[str]) -> bool:
    if not configured:
        return False
    token_bytes = token.encode("utf-8")
    for candidate in configured:
        if hmac.compare_digest(token_bytes, candidate.encode("utf-8")):
            return True
    return False


def require_partner(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Validate bearer token and apply partner export rate limit."""
    tokens: list[str] = getattr(request.app.state, "partner_export_tokens", [])
    token = extract_bearer(authorization)
    if token is None or not verify_partner_token(token, tokens):
        raise HTTPException(status_code=401, detail="unauthorized")

    take = getattr(request.app.state, "partner_export_take", None)
    if take is not None:
        allowed, retry_after = take(f"partner:{token_fingerprint(token)}")
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="rate limit exceeded",
                headers={"Retry-After": str(retry_after)},
            )
    return token


PartnerAuth = Annotated[str, Depends(require_partner)]
