"""
Config
======
Every secret comes from environment variables (.env), never hardcoded.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
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
    APP_SECRET_KEY: str = _require("APP_SECRET_KEY")
    TOKEN_EXPIRY_MINUTES: int = int(os.environ.get("TOKEN_EXPIRY_MINUTES", "60"))

    # --- Webhook signing (HMAC) ---
    WEBHOOK_SIGNING_SECRET: str = _require("WEBHOOK_SIGNING_SECRET")

    # --- X (Twitter) OAuth 2.0 User Context ---
    # From the scopes/consent flow (tweet.write, users.read, etc.)
    X_OAUTH2_ACCESS_TOKEN: str = os.environ.get("X_OAUTH2_ACCESS_TOKEN", "")
    X_OAUTH2_REFRESH_TOKEN: str = os.environ.get("X_OAUTH2_REFRESH_TOKEN", "")

    # --- Mock platform (built for the capstone's rate-limit/webhook demo) ---
    MOCK_PLATFORM_RATE_LIMIT: int = int(os.environ.get("MOCK_PLATFORM_RATE_LIMIT", "5"))
    MOCK_PLATFORM_RATE_WINDOW_SECONDS: int = int(
        os.environ.get("MOCK_PLATFORM_RATE_WINDOW_SECONDS", "60")
    )


settings = Settings()
