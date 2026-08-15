"""
X (Twitter) Adapter — REAL platform, OAuth 2.0 User Context
==============================================================
Uses a single OAuth 2.0 access token (obtained via the scopes/consent
flow — tweet.write, users.read, etc.) instead of OAuth 1.0a's four-part
consumer key/secret + access token/secret.
"""

import tweepy
from app.config import settings
from app.adapters.base import PlatformAdapter, PlatformResult


class XAdapter(PlatformAdapter):
    name = "x"

    def __init__(self):
        self._client = None
        if settings.X_OAUTH2_ACCESS_TOKEN:
            self._client = tweepy.Client(access_token=settings.X_OAUTH2_ACCESS_TOKEN)

    async def publish(self, user_id: str, message: str) -> PlatformResult:
        if self._client is None:
            return PlatformResult(
                success=False,
                error="X OAuth 2.0 access token not configured in .env",
            )

        try:
            response = self._client.create_tweet(text=message)
            tweet_id = response.data["id"]
            return PlatformResult(success=True, platform_post_id=str(tweet_id))

        except tweepy.TooManyRequests as e:
            retry_after = int(e.response.headers.get("Retry-After", 60)) if e.response else 60
            return PlatformResult(
                success=False, error="Rate limited by X", retry_after_seconds=retry_after
            )

        except tweepy.Forbidden as e:
            return PlatformResult(success=False, error=f"X rejected the request: {e}")

        except tweepy.Unauthorized as e:
            return PlatformResult(
                success=False,
                error=f"X auth failed — access token may be expired, use the refresh token to get a new one: {e}",
            )

        except Exception as e:  # noqa: BLE001
            return PlatformResult(success=False, error=f"Unexpected X API error: {e}")
