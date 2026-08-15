"""
Auth Router
===========
POST /auth/token — the "token endpoint" the capstone brief requires.

For this demo, a user proves who they are with an app-issued API key
(stored hashed in Mongo — see database seeding note in README) and
receives a short-lived bearer token to use on /publish.
"""

import hashlib
from fastapi import APIRouter, HTTPException, status
from app.models import TokenRequest, TokenResponse
from app.database import users
from app.security import issue_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


def _hash_api_key(raw_key: str) -> str:
    """API keys are stored as salted hashes, never in plaintext — so a
    database leak alone doesn't expose usable credentials."""
    return hashlib.sha256((raw_key + settings.APP_SECRET_KEY).encode()).hexdigest()


@router.post("/token", response_model=TokenResponse)
async def get_token(body: TokenRequest):
    user = await users.find_one({"user_id": body.user_id})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown user_id")

    if user["api_key_hash"] != _hash_api_key(body.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    token = issue_token(body.user_id)
    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.TOKEN_EXPIRY_MINUTES,
    )
