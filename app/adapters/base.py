"""
Base Adapter
============
Every platform (X, Mock, and any future one — Telegram, Discord, Mastodon)
implements this same interface. The publish endpoint doesn't need to know
which platform it's talking to; it just calls .publish() and gets a
PlatformResult back. This is what "mock platform adapters" means in the
brief: a consistent shape regardless of what's underneath.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PlatformResult:
    success: bool
    platform_post_id: Optional[str] = None
    error: Optional[str] = None
    retry_after_seconds: Optional[int] = None  # set when rate-limited


class PlatformAdapter(ABC):
    name: str

    @abstractmethod
    async def publish(self, user_id: str, message: str) -> PlatformResult:
        """Attempt to publish `message` as `user_id`. Never raises for
        expected failure modes (rate limit, auth failure) — those come
        back as a PlatformResult so the caller can handle them cleanly."""
        raise NotImplementedError
