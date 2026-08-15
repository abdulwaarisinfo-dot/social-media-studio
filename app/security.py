"""
Security
========
- Short-lived bearer tokens (HMAC-signed, not a real JWT library dependency
  needed for this scope, but the same signed-payload principle).
- HMAC-SHA256 signing/verification for outgoing webhook callbacks, so a
  receiver can prove a callback genuinely came from this service.
- API keys are never logged or returned in responses.
"""

import hmac
import hashlib
import time
import json
import base64
from fastapi import Header, HTTPException, status
from app.config import settings


# ---------------------------------------------------------------------------
# Bearer tokens (issued by POST /auth/token)
# ---------------------------------------------------------------------------

def issue_token(user_id: str) -> str:
    """Create a signed, expiring token. Payload is base64'd JSON; signature
    is HMAC-SHA256 over that payload using the app secret. Nobody can forge
    a token without knowing APP_SECRET_KEY, and nobody can extend an
    expired one without re-authenticating."""
    payload = {
        "user_id": user_id,
        "exp": int(time.time()) + settings.TOKEN_EXPIRY_MINUTES * 60,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()
    signature = _sign(payload_b64)
    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> str:
    """Returns user_id if valid; raises 401 otherwise."""
    try:
        payload_b64, signature = token.split(".")
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token")

    expected_sig = _sign(payload_b64)
    if not hmac.compare_digest(signature, expected_sig):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token signature")

    payload = json.loads(base64.urlsafe_b64decode(payload_b64))
    if payload["exp"] < int(time.time()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")

    return payload["user_id"]


def _sign(data: str) -> str:
    return hmac.new(
        settings.APP_SECRET_KEY.encode(), data.encode(), hashlib.sha256
    ).hexdigest()


async def get_current_user(authorization: str = Header(...)) -> str:
    """FastAPI dependency: extracts and verifies the bearer token from the
    Authorization header. Use as: user_id: str = Depends(get_current_user)"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Expected 'Bearer <token>'")
    token = authorization.removeprefix("Bearer ").strip()
    return verify_token(token)


# ---------------------------------------------------------------------------
# HMAC-signed webhook callbacks
# ---------------------------------------------------------------------------

def sign_webhook_payload(payload: dict) -> str:
    """Sign a webhook body so the receiver can verify authenticity."""
    body = json.dumps(payload, sort_keys=True, default=str)
    return hmac.new(
        settings.WEBHOOK_SIGNING_SECRET.encode(), body.encode(), hashlib.sha256
    ).hexdigest()


def verify_webhook_signature(payload: dict, signature: str) -> bool:
    expected = sign_webhook_payload(payload)
    return hmac.compare_digest(expected, signature)
