"""
Run this once to create a test user you can authenticate as.

Usage:
    python -m scripts.seed_user my_user_id my-secret-api-key

The API key you choose here is what you'll POST to /auth/token later.
It's hashed before storage — the plaintext key is never saved.
"""

import sys
import asyncio
import hashlib

sys.path.append(".")
from app.database import users
from app.config import settings


def _hash_api_key(raw_key: str) -> str:
    return hashlib.sha256((raw_key + settings.APP_SECRET_KEY).encode()).hexdigest()


async def main(user_id: str, api_key: str):
    await users.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "api_key_hash": _hash_api_key(api_key)}},
        upsert=True,
    )
    print(f"Seeded user '{user_id}'. Use this api_key at POST /auth/token: {api_key}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: python -m scripts.seed_user <user_id> <api_key>")
    asyncio.run(main(sys.argv[1], sys.argv[2]))
