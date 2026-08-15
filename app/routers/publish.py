"""
Publish Router
==============
POST /publish — the "publish endpoint honouring an Idempotency-Key" the
capstone brief requires.

Flow:
  1. Require an Idempotency-Key header on every request.
  2. Look it up (scoped per user) in Mongo before doing anything else.
     - Found  -> return the original result. Never call the platform twice.
     - Not found -> proceed, then record the result under that key.
  3. Dispatch to the right platform adapter (x / mock).
  4. If the platform reports a rate limit, surface it as a real 429 with
     Retry-After — don't swallow it as a generic 500.
  5. Log every attempt (success or failure) to publish_log for audit.

The unique index on (user_id, idempotency_key) in database.py is what
makes step 2 safe even if two identical requests race each other —
whichever loses the race hits a duplicate-key error and simply reads
back the winner's result.
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pymongo.errors import DuplicateKeyError

from app.models import PublishRequest, PublishResponse
from app.database import idempotency_records, publish_log
from app.security import get_current_user
from app.adapters.x_adapter import XAdapter
from app.adapters.mock_adapter import MockPlatformAdapter

router = APIRouter(prefix="/publish", tags=["publish"])

_x_adapter = XAdapter()


def _get_adapter(platform: str):
    if platform == "x":
        return _x_adapter
    if platform == "mock":
        return MockPlatformAdapter(webhook_url=None)  # set a real URL to see the callback
    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown platform: {platform}")


@router.post("", response_model=PublishResponse)
async def publish(
    body: PublishRequest,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    user_id: str = Depends(get_current_user),
):
    # --- Step 1: idempotency check ---
    existing = await idempotency_records.find_one(
        {"user_id": user_id, "idempotency_key": idempotency_key}
    )
    if existing:
        return PublishResponse(
            status="duplicate_ignored",
            platform=existing["platform"],
            platform_post_id=existing.get("platform_post_id"),
            idempotency_key=idempotency_key,
            published_at=existing["published_at"],
        )

    # --- Step 2: dispatch to the real adapter ---
    adapter = _get_adapter(body.platform)
    result = await adapter.publish(user_id=user_id, message=body.message)

    now = datetime.now(timezone.utc)

    if not result.success:
        await publish_log.insert_one({
            "user_id": user_id, "platform": body.platform, "message": body.message,
            "idempotency_key": idempotency_key, "success": False,
            "error": result.error, "at": now,
        })
        if result.retry_after_seconds is not None:
            response.headers["Retry-After"] = str(result.retry_after_seconds)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"error": result.error, "retry_after_seconds": result.retry_after_seconds},
            )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=result.error)

    # --- Step 3: record success under this idempotency key (race-safe) ---
    record = {
        "user_id": user_id,
        "idempotency_key": idempotency_key,
        "platform": body.platform,
        "platform_post_id": result.platform_post_id,
        "message": body.message,
        "published_at": now,
    }
    try:
        await idempotency_records.insert_one(record)
    except DuplicateKeyError:
        # Lost a race to a concurrent identical request — read back the winner.
        existing = await idempotency_records.find_one(
            {"user_id": user_id, "idempotency_key": idempotency_key}
        )
        return PublishResponse(
            status="duplicate_ignored",
            platform=existing["platform"],
            platform_post_id=existing.get("platform_post_id"),
            idempotency_key=idempotency_key,
            published_at=existing["published_at"],
        )

    await publish_log.insert_one({**record, "success": True})

    return PublishResponse(
        status="published",
        platform=body.platform,
        platform_post_id=result.platform_post_id,
        idempotency_key=idempotency_key,
        published_at=now,
    )
