# Social Media Studio

A backend publishing service with pluggable platform adapters, idempotent publish handling, rate-limit-aware error responses, and HMAC-signed delivery webhooks — built for the Backend AI Engineering capstone.

**Live:** https://social-media-studio-00j6.onrender.com
**Docs (interactive):** https://social-media-studio-00j6.onrender.com/docs

## What it does and for whom

This is a backend service for developers who need to publish content to multiple social platforms reliably — the kind of service that sits behind a "schedule this post" button in a tool like Buffer or Hootsuite. It solves the unglamorous but critical part of that problem: making sure a publish request that gets retried (slow network, user double-clicking, a timeout) never results in the same post going out twice, and that a platform's rate limit gets surfaced as a real, actionable error instead of a silent failure or a crash.

It's aimed at other backend developers — the audience is "someone who needs to add reliable social publishing to their own project and wants a working reference for the pattern," not end users.

## Setup a stranger could follow

```bash
git clone https://github.com/abdulwaarisinfo-dot/social-media-studio.git
cd social-media-studio
pip install -r requirements.txt --break-system-packages

cp .env.example .env
# fill in MONGODB_URI (free tier at mongodb.com/cloud/atlas works),
# generate APP_SECRET_KEY and WEBHOOK_SIGNING_SECRET with:
#   python -c "import secrets; print(secrets.token_hex(32))"
# and X_OAUTH2_ACCESS_TOKEN / X_OAUTH2_REFRESH_TOKEN from
# developer.x.com if you want the real X adapter to work
# (the mock adapter works with no external credentials at all)

uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs` for the interactive API explorer.

## Usage examples

Register a user, get a token, publish (with the idempotency key that prevents duplicate posts):

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo_user", "api_key": "choose-any-8-char-key"}'

curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"user_id": "demo_user", "api_key": "choose-any-8-char-key"}'
# -> returns access_token

curl -X POST http://localhost:8000/publish \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: order-001" \
  -H "Content-Type: application/json" \
  -d '{"platform": "mock", "message": "Hello World"}'
```

Retrying the exact same request with the same `Idempotency-Key` returns `"status": "duplicate_ignored"` instead of publishing a second time — this is the core behavior the whole project exists to demonstrate.

## Architecture

```
Client
  |
  v
POST /publish  (requires Idempotency-Key + Bearer token)
  |
  v
Idempotency check (MongoDB, unique index on user_id + key)
  |-- seen before -----> return original result, STOP
  |
  v (new request)
Platform adapter dispatch
  |-- "x"    -> XAdapter (real, OAuth 2.0 -> X API)
  |-- "mock" -> MockPlatformAdapter (rate limit + HMAC webhook)
  |
  v
Result recorded in MongoDB, response returned
```

Both adapters implement the same `PlatformAdapter` interface (`app/adapters/base.py`), so `/publish` never branches on which platform it's talking to — adding Telegram or Discord later is one new adapter file, no changes to the publish endpoint itself.

## v2 eval results

I tested both code paths for real rather than only unit-testing in isolation:

- **Mock platform**: ran the full flow (register -> token -> publish -> duplicate retry -> rate limit) via `curl`/`Invoke-RestMethod` against the deployed Render instance. Confirmed: a repeated `Idempotency-Key` returns `duplicate_ignored` and does not create a second record; exceeding `MOCK_PLATFORM_RATE_LIMIT` (5 requests / 60s) returns a real `429` with a `Retry-After` header.
- **Real X platform**: switched the adapter from OAuth 1.0a to OAuth 2.0 user-context after discovering my initial token only had read scope. After regenerating the token with `tweet.write` scope, a real, single test post was published successfully to X via the deployed service — verified by checking `platform_post_id` in the response and confirming the post on X directly.
- **Security functions tested in isolation**: token issue/verify round-trip, tampered-token rejection, webhook signature verify/tamper-detection — all passed (see `app/security.py`; verified interactively before deployment).

## Limitations

Being upfront about what this doesn't do:

- **Only one real platform is wired up (X)**, not the full "publish everywhere" experience a production tool would need — Telegram/Discord/Mastodon adapters would follow the same interface but aren't implemented yet.
- **No refresh-token rotation.** X's OAuth 2.0 access token expires (~2 hours); the code doesn't yet auto-refresh it using the stored refresh token, so a long-running deployment would eventually need a manual token refresh.
- **Idempotency key generation is left to the caller.** The service enforces uniqueness once a key is provided, but doesn't validate that the caller derived the key sensibly (e.g. from message content + user, per the design intent) — a caller could accidentally reuse a key across genuinely different posts.
- **Rate limiting on the mock platform is in-memory-adjacent (Mongo-backed) per-process**, not a distributed rate limiter — fine for a single-instance demo, not for horizontally-scaled production use.
- **No automated test suite.** Testing so far has been manual/interactive (curl and PowerShell against the live deployment), not a `pytest` suite — that would be the next thing added.

## What I built with AI and how

I built this with Claude as a hands-on pair-programming partner: I described the capstone requirements (idempotency, rate limiting, HMAC webhooks, a real platform integration) and Claude generated the initial project structure, the adapter pattern, and the security module. From there I drove the actual debugging myself — diagnosing and fixing the Render Python-version build failure, discovering and fixing the OAuth 1.0a vs OAuth 2.0 mismatch after getting real 401 errors from X, and working through the PowerShell/curl header-passing issues during live testing. I verified the security logic myself by running the token and webhook signing functions interactively and checking tamper-detection worked before trusting it. Claude explained concepts (idempotency, OAuth flows, rate-limit patterns) as we went, which is what let me debug the auth mismatch myself once I understood what OAuth 2.0 user-context actually required.
