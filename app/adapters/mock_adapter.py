"""
Mock Platform Adapter
======================
A self-built fake platform used to demonstrate — without spending real
X API credits or hitting a live platform's actual rate limits — the
specific behaviours the capstone brief asks for:

  - a token endpoint (see routers/auth.py, shared across platforms)
  - a publish endpoint that honours Idempotency-Key (see routers/publish.py)
  - a rate-limit switch that returns 429 with Retry-After
  - an HMAC-signed callback to a webhook, confirming delivery

This adapter simulates network latency and a sliding-window rate limit
backed by MongoDB, then "delivers" by firing a signed webhook callback —
the same shape a real platform's async delivery confirmation would take.
"""

import asyncio
import time
import uuid
import httpx

from app.database import rate_limit_buckets
from app.config import settings
from app.security import sign_webhook_payload
from app.adapters.base import PlatformAdapter, PlatformResult


class MockPlatformAdapter(PlatformAdapter):
    name = "mock"

    def __init__(self, webhook_url: str | None = None):
        # Where this adapter fires its delivery-confirmation webhook.
        # In production this would be the caller's registered webhook URL;
        # for local testing, point it at a webhook.site URL or your own
        # /webhooks/mock-platform endpoint.
        self.webhook_url = webhook_url

    async def publish(self, user_id: str, message: str) -> PlatformResult:
        # 1. Rate-limit check (sliding window per user)
        limited, retry_after = await self._check_rate_limit(user_id)
        if limited:
            return PlatformResult(
                success=False,
                error="Rate limited by mock platform",
                retry_after_seconds=retry_after,
            )

        # 2. Simulate realistic network latency
        await asyncio.sleep(0.3)

        # 3. "Publish" — generate a fake but unique post id
        post_id = f"mock_{uuid.uuid4().hex[:12]}"

        # 4. Fire the signed webhook callback confirming delivery
        if self.webhook_url:
            await self._send_signed_callback(post_id)

        return PlatformResult(success=True, platform_post_id=post_id)

    async def _check_rate_limit(self, user_id: str) -> tuple[bool, int | None]:
        now = time.time()
        window_start = now - settings.MOCK_PLATFORM_RATE_WINDOW_SECONDS
        bucket_key = f"mock:{user_id}"

        doc = await rate_limit_buckets.find_one({"bucket_key": bucket_key})
        timestamps = [t for t in (doc["timestamps"] if doc else []) if t > window_start]

        if len(timestamps) >= settings.MOCK_PLATFORM_RATE_LIMIT:
            oldest = min(timestamps)
            retry_after = int(oldest + settings.MOCK_PLATFORM_RATE_WINDOW_SECONDS - now) + 1
            return True, max(retry_after, 1)

        timestamps.append(now)
        await rate_limit_buckets.update_one(
            {"bucket_key": bucket_key},
            {"$set": {"bucket_key": bucket_key, "timestamps": timestamps}},
            upsert=True,
        )
        return False, None

    async def _send_signed_callback(self, post_id: str) -> None:
        payload = {
            "event": "post.delivered",
            "post_id": post_id,
            "platform": self.name,
            "delivered_at": time.time(),
        }
        signature = sign_webhook_payload(payload)
        headers = {"X-Signature-HMAC-SHA256": signature}

        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.post(self.webhook_url, json=payload, headers=headers)
        except httpx.HTTPError:
            # Delivery confirmation failing shouldn't fail the publish call
            # itself — the post already succeeded. Log and move on.
            pass
