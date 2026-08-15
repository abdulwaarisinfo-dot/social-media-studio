"""
Auth Router
===========
POST /auth/register — self-serve: create a user with a chosen api_key,
straight from /docs, no terminal needed.

POST /auth/token — exchange (user_id, api_key) for a short-lived bearer
token, used on /publish.
"""

import hashlib
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.models import TokenRequest, TokenResponse
from app.database import users
from app.security import issue_token
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    api_key: str = Field(..., min_length=8, description="Choose any key, at least 8 characters")


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256((raw_key + settings.APP_SECRET_KEY).encode()).hexdigest()


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    """Create (or update) a user directly from /docs — no terminal needed."""
    await users.update_one(
        {"user_id": body.user_id},
        {"$set": {"user_id": body.user_id, "api_key_hash": _hash_api_key(body.api_key)}},
        upsert=True,
    )
    return {"message": f"User '{body.user_id}' registered. Now call /auth/token with these credentials."}


@router.post("/token", response_model=TokenResponse)
async def get_token(body: TokenRequest):
    user = await users.find_one({"user_id": body.user_id})
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown user_id — call /auth/register first")

    if user["api_key_hash"] != _hash_api_key(body.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")

    token = issue_token(body.user_id)
    return TokenResponse(
        access_token=token,
        expires_in_minutes=settings.TOKEN_EXPIRY_MINUTES,
    )
