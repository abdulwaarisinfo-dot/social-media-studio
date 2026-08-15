"""
Social Media Studio — main entrypoint
======================================
Run with: uvicorn app.main:app --reload
Docs at:  http://localhost:8000/docs
"""

from fastapi import FastAPI
from app.database import ensure_indexes
from app.routers import auth, publish, webhooks

app = FastAPI(
    title="Social Media Studio",
    description=(
        "A backend publishing service with pluggable platform adapters, "
        "idempotent publish handling, rate-limit-aware error responses, "
        "and HMAC-signed delivery webhooks."
    ),
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(publish.router)
app.include_router(webhooks.router)


@app.on_event("startup")
async def on_startup():
    await ensure_indexes()


@app.get("/health")
async def health():
    return {"status": "ok"}
