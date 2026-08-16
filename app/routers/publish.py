"""
Publish Router
==============

POST /publish — publish endpoint honouring an Idempotency-Key.

Flow:
  1. Require an Idempotency-Key header.
  2. Look it up in MongoDB, scoped per user.
     - Found  -> return original result.
     - Not found -> continue to platform adapter.
  3. Dispatch to the requested platform adapter.
  4. Rate limits are returned as HTTP 429 with Retry-After.
  5. Every publish attempt is logged to publish_log.
  6. Successful results are stored for idempotent replay.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.models import PublishRequest, PublishResponse
from app.database import idempotency_records, publish_log
from app.security import get_current_user
from app.adapters.x_adapter import XAdapter
from app.adapters.mock_adapter import MockPlatformAdapter


router = APIRouter(
    prefix="/publish",
    tags=["publish"],
)


# ---------------------------------------------------------
# Platform adapters
# ---------------------------------------------------------

_x_adapter = XAdapter()


def _get_adapter(platform: str):
    """
    Return the adapter for the requested platform.
    """

    if platform == "x":
        return _x_adapter

    if platform == "mock":
        # Webhook URL will be configured separately.
        return MockPlatformAdapter(webhook_url=None)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unknown platform: {platform}",
    )


# ---------------------------------------------------------
# POST /publish
# ---------------------------------------------------------

@router.post(
    "",
    response_model=PublishResponse,
)
async def publish(
    body: PublishRequest,
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key",
    ),
    user_id: str = Depends(get_current_user),
):
    """
    Publish a message to the requested platform.

    Idempotency:
        The same user + Idempotency-Key will never create
        another platform post.

    Rate limiting:
        Platform rate-limit responses are converted into
        HTTP 429 with a Retry-After header.
    """

    # =====================================================
    # STEP 1 — IDEMPOTENCY CHECK
    # =====================================================

    existing = await idempotency_records.find_one(
        {
            "user_id": user_id,
            "idempotency_key": idempotency_key,
        }
    )

    if existing:
        return PublishResponse(
            status="duplicate_ignored",
            platform=existing["platform"],
            platform_post_id=existing.get("platform_post_id"),
            idempotency_key=idempotency_key,
            published_at=existing["published_at"],
        )

    # =====================================================
    # STEP 2 — GET PLATFORM ADAPTER
    # =====================================================

    adapter = _get_adapter(body.platform)

    # =====================================================
    # STEP 3 — PUBLISH
    # =====================================================

    result = await adapter.publish(
        user_id=user_id,
        message=body.message,
    )

    now = datetime.now(timezone.utc)

    # =====================================================
    # STEP 4 — HANDLE PLATFORM FAILURE
    # =====================================================

    if not result.success:

        # Audit log
        await publish_log.insert_one(
            {
                "user_id": user_id,
                "platform": body.platform,
                "message": body.message,
                "idempotency_key": idempotency_key,
                "success": False,
                "error": result.error,
                "at": now,
            }
        )

        # -------------------------------------------------
        # RATE LIMIT → 429 + Retry-After
        # -------------------------------------------------

        if result.retry_after_seconds is not None:

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": result.error,
                    "retry_after_seconds": result.retry_after_seconds,
                },
                headers={
                    "Retry-After": str(
                        result.retry_after_seconds
                    )
                },
            )

        # -------------------------------------------------
        # OTHER PLATFORM FAILURE → 502
        # -------------------------------------------------

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=result.error,
        )

    # =====================================================
    # STEP 5 — CREATE IDEMPOTENCY RECORD
    # =====================================================

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

        # -------------------------------------------------
        # Another identical request won the race.
        # Read its result instead of publishing again.
        # -------------------------------------------------

        existing = await idempotency_records.find_one(
            {
                "user_id": user_id,
                "idempotency_key": idempotency_key,
            }
        )

        if existing:
            return PublishResponse(
                status="duplicate_ignored",
                platform=existing["platform"],
                platform_post_id=existing.get(
                    "platform_post_id"
                ),
                idempotency_key=idempotency_key,
                published_at=existing["published_at"],
            )

        # Extremely unlikely fallback if the winning
        # record cannot be found.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Idempotency record conflict",
        )

    # =====================================================
    # STEP 6 — SUCCESS AUDIT LOG
    # =====================================================

    await publish_log.insert_one(
        {
            **record,
            "success": True,
        }
    )

    # =====================================================
    # STEP 7 — RESPONSE
    # =====================================================

    return PublishResponse(
        status="published",
        platform=body.platform,
        platform_post_id=result.platform_post_id,
        idempotency_key=idempotency_key,
        published_at=now,
    )
