"""
Webhook Receiver
================
Demonstrates the receiving side of the "HMAC-signed callback" requirement:
verifies the X-Signature-HMAC-SHA256 header before trusting the payload.
Point the mock adapter's webhook_url at this endpoint locally to see the
full round trip.
"""

from fastapi import APIRouter, Header, HTTPException, Request, status
from app.security import verify_webhook_signature

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/mock-platform")
async def receive_mock_platform_webhook(
    request: Request,
    x_signature_hmac_sha256: str = Header(..., alias="X-Signature-HMAC-SHA256"),
):
    payload = await request.json()

    if not verify_webhook_signature(payload, x_signature_hmac_sha256):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid webhook signature")

    # Signature verified — safe to trust and act on the payload.
    print(f"[webhook verified] post {payload['post_id']} delivered on {payload['platform']}")
    return {"received": True}
