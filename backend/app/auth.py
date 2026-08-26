import os
import hmac
from fastapi import Header, Query, HTTPException, status

SHARED_SECRET = os.environ.get("SHARED_SECRET", "")


def require_secret(
    x_frz_key: str | None = Header(default=None),
    k: str | None = Query(default=None),
) -> None:
    """Reject requests that don't carry the shared secret.

    Accepts either the ``X-Frz-Key`` header (used by the web app once it
    stashes the secret in localStorage) or the ``?k=`` query param (used by
    QR-code URLs so a fresh browser session works)."""
    if not SHARED_SECRET:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "server missing SHARED_SECRET")
    supplied = x_frz_key or k or ""
    if not hmac.compare_digest(supplied, SHARED_SECRET):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad or missing key")
