"""
X (Twitter) Adapter — REAL platform
====================================
Publishes a genuine post to X using OAuth 1.0a user-context auth via
tweepy. This is the "at least one real free platform" requirement —
credentials come entirely from .env, never hardcoded.

Note: X's write API is a paid, rate-limited resource as of 2026. This
adapter still demonstrates the correct pattern (real auth, real HTTP call,
real error handling) — swap in Telegram/Discord/Mastodon credentials in
.env and a near-identical adapter would work for those instead.
"""

import tweepy
from app.config import settings
from app.adapters.base import PlatformAdapter, PlatformResult


class XAdapter(PlatformAdapter):
    name = "x"

    def __init__(self):
        self._client = None
        if all([
            settings.X_API_KEY, settings.X_API_SECRET,
            settings.X_ACCESS_TOKEN, settings.X_ACCESS_TOKEN_SECRET,
        ]):
            self._client = tweepy.Client(
                consumer_key=settings.X_API_KEY,
                consumer_secret=settings.X_API_SECRET,
                access_token=settings.X_ACCESS_TOKEN,
                access_token_secret=settings.X_ACCESS_TOKEN_SECRET,
            )

    async def publish(self, user_id: str, message: str) -> PlatformResult:
        if self._client is None:
            return PlatformResult(
                success=False,
                error="X credentials not configured in .env — see .env.example",
            )

        try:
            response = self._client.create_tweet(text=message)
            tweet_id = response.data["id"]
            return PlatformResult(success=True, platform_post_id=str(tweet_id))

        except tweepy.TooManyRequests as e:
            # X returned a real 429 — surface it the same way our mock does,
            # so the caller handles both platforms identically.
            retry_after = int(e.response.headers.get("Retry-After", 60)) if e.response else 60
            return PlatformResult(
                success=False, error="Rate limited by X", retry_after_seconds=retry_after
            )

        except tweepy.Forbidden as e:
            return PlatformResult(success=False, error=f"X rejected the request: {e}")

        except Exception as e:  # noqa: BLE001 - surface unexpected errors, don't crash the request
            return PlatformResult(success=False, error=f"Unexpected X API error: {e}")
