"""
Database
========
Async MongoDB Atlas connection (Motor driver) and the collections this
service uses.

Collections:
- idempotency_records : one document per Idempotency-Key we've ever seen,
                         so retries return the original result instead of
                         re-publishing.
- users                : per-user platform credentials (e.g. their X tokens),
                         so each user's posts go to *their own* account.
- publish_log          : an audit trail of every publish attempt.
- rate_limit_buckets   : sliding-window counters for the mock platform's
                         429 / Retry-After simulation.
"""

from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings

_client = AsyncIOMotorClient(settings.MONGODB_URI)
db = _client[settings.MONGODB_DB_NAME]

idempotency_records = db["idempotency_records"]
users = db["users"]
publish_log = db["publish_log"]
rate_limit_buckets = db["rate_limit_buckets"]


async def ensure_indexes():
    """Call once at startup. Unique index on idempotency key is what
    actually makes duplicate-prevention airtight even under concurrent
    requests (not just an application-level if-check)."""
    await idempotency_records.create_index(
        [("user_id", 1), ("idempotency_key", 1)], unique=True
    )
    await users.create_index("user_id", unique=True)
    await rate_limit_buckets.create_index("bucket_key")
