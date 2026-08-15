"""Request/response schemas. Pydantic validates every incoming payload,
so malformed requests are rejected before they reach any business logic."""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from datetime import datetime


class TokenRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)
    api_key: str = Field(..., min_length=8, description="This user's app-issued API key")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_minutes: int


class PublishRequest(BaseModel):
    platform: Literal["x", "mock"] = Field(..., description="Which adapter to publish through")
    message: str = Field(..., min_length=1, max_length=280)

    @field_validator("message")
    @classmethod
    def no_blank_message(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("message cannot be blank")
        return v


class PublishResponse(BaseModel):
    status: Literal["published", "duplicate_ignored"]
    platform: str
    platform_post_id: Optional[str] = None
    idempotency_key: str
    published_at: datetime


class WebhookCallback(BaseModel):
    """What the mock platform sends back to confirm delivery."""
    event: str
    post_id: str
    platform: str
    delivered_at: datetime
    signature: str  # HMAC-SHA256 hex digest, verified by the receiver
