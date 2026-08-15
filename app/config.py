"""
Config
======
Every secret comes from environment variables (.env), never hardcoded.
This is the single place the rest of the app reads configuration from.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # reads .env in the project root, if present


def _require(name: str) -> str:
    """Fail loudly at startup if a required secret is missing, instead of
    failing confusingly later when something tries to use it."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            f"Copy .env.example to .env and fill it in."
        )
    return value


class Settings:
    # --- MongoDB Atlas ---
    MONGODB_URI: str = _require("MONGODB_URI")
    MONGODB_DB_NAME: str = os.environ.get("MONGODB_DB_NAME", "social_media_studio")

    # --- App / API auth ---
    # Used to sign the short-lived tokens this service issues from /auth/token
    APP_SECRET_KEY: str = _require("APP_SECRET_KEY")
    TOKEN_EXPIRY_MINUTES: int = int(os.environ.get("TOKEN_EXPIRY_MINUTES", "60"))

    # --- Webhook signing (HMAC) ---
    # Used to sign outgoing webhook callbacks so the receiver can verify
    # the callback genuinely came from this service and wasn't forged.
    WEBHOOK_SIGNING_SECRET: str = _require("WEBHOOK_SIGNING_SECRET")

    # --- X (Twitter) API credentials ---
    # OAuth 1.0a user-context credentials (needed to POST as a specific user).
    X_API_KEY: str = os.environ.get("X_API_KEY", "")
    X_API_SECRET: str = os.environ.get("X_API_SECRET", "")
    X_ACCESS_TOKEN: str = os.environ.get("X_ACCESS_TOKEN", "")
    X_ACCESS_TOKEN_SECRET: str = os.environ.get("X_ACCESS_TOKEN_SECRET", "")

    # --- Mock platform (built for the capstone's rate-limit/webhook demo) ---
    MOCK_PLATFORM_RATE_LIMIT: int = int(os.environ.get("MOCK_PLATFORM_RATE_LIMIT", "5"))
    MOCK_PLATFORM_RATE_WINDOW_SECONDS: int = int(
        os.environ.get("MOCK_PLATFORM_RATE_WINDOW_SECONDS", "60")
    )


settings = Settings()
