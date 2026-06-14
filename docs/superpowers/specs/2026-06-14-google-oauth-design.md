# Google OAuth (verify ID token) — design

- **Date:** 2026-06-14
- **Phase:** 1 (Core mechanic) — auth
- **Status:** Approved, ready for implementation plan

## Context

The app has password auth (`/auth/register|login|refresh|logout|me`) with an access/refresh JWT pair, and messages are now tied to user accounts. The `User` model already carries a `google_sub` column (`String(255)`, nullable, unique) and a nullable `password_hash`, so a Google-only account (no password) is already representable. This milestone adds "Sign in with Google".

The frontend does not exist yet (later milestone), which drives the choice of flow: the backend verifies a Google **ID token** rather than running a server-side redirect/callback dance.

## Goals

- A single endpoint, `POST /auth/google`, that accepts a Google ID token, verifies it, resolves (or creates) the matching `User`, and returns our own access+refresh token pair — identical in shape to `/auth/login`.
- First-time Google users get a usable, unique `username` automatically (so they can send and be addressed as recipients).
- A Google sign-in whose verified email matches an existing password account links to that account.
- No new auth library churn beyond Google's official verifier.

## Non-goals (out of scope)

- Server-side Authorization Code / redirect-callback flow (no `client_secret`, no redirect URIs).
- A "choose your own username" step after first login (auto-generation only; a rename feature can come with the frontend).
- Verifying emails on the password-registration path (a known gap; see Security caveat).
- Rewriting a stored email when a Google account's email later changes (we match by stable `sub`).
- Any model or schema migration (none needed).

## Decisions

| Decision | Choice |
|---|---|
| Flow | Verify a Google **ID token** posted by the client; no redirect/callback |
| Endpoint | `POST /auth/google` `{id_token}` → `TokenPairOut` |
| Username | Auto-generated from email/name, sanitized + collision-suffixed |
| Account linking | Auto-link to an existing account by **verified** email |
| Verify library | `google-auth` official (`id_token.verify_oauth2_token`) + `requests` transport |
| Code structure | Dedicated `app/google_auth.py` seam (no DB); route orchestrates in `auth_routes.py` |
| Model/schema | No migration — `google_sub`/nullable `password_hash` already exist |

## Detailed design

### Dependencies & config

- `backend/requirements.txt`: add `google-auth` and `requests` (the HTTP transport that `verify_oauth2_token` uses).
- New env var `GOOGLE_CLIENT_ID`, read at import in `google_auth.py` (mirrors `JWT_SECRET` in `security.py`). If unset/empty, the verifier raises `RuntimeError` and the endpoint returns a clear **500** — it never silently accepts a token.

### `app/google_auth.py` — verification seam (no DB access)

Mirrors `security.py`'s "auth primitives, no DB" boundary.

```python
"""Google ID token verification. No DB access."""
import os
from dataclasses import dataclass

from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
_ACCEPTED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
# Reused for HTTP connection pooling. NOTE: this does NOT cache Google's signing
# certs — verify_oauth2_token re-fetches them each call. Fine for dev; a
# CacheControl-wrapped session is a future optimization if it ever matters.
_transport = google_requests.Request()


class InvalidGoogleToken(Exception):
    """Missing, malformed, expired, or untrusted Google ID token."""


class GoogleVerifyUnavailable(Exception):
    """Couldn't reach Google to fetch certs / verify (transient transport error)."""


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    email_verified: bool
    name: str | None


def verify_google_id_token(token: str) -> GoogleIdentity:
    if not GOOGLE_CLIENT_ID:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured")
    try:
        claims = google_id_token.verify_oauth2_token(token, _transport, GOOGLE_CLIENT_ID)
    except google_exceptions.TransportError as exc:   # can't reach Google (must precede GoogleAuthError)
        raise GoogleVerifyUnavailable(str(exc)) from exc
    except (ValueError, google_exceptions.GoogleAuthError) as exc:
        # ValueError: bad signature/aud/exp/format. GoogleAuthError: wrong issuer
        # — verify_oauth2_token checks iss itself and raises this, not ValueError.
        raise InvalidGoogleToken(str(exc)) from exc
    # Defensive (older google-auth versions didn't check iss inside verify):
    if claims.get("iss") not in _ACCEPTED_ISSUERS:
        raise InvalidGoogleToken("untrusted issuer")
    sub, email = claims.get("sub"), claims.get("email")
    if not sub or not email:
        raise InvalidGoogleToken("missing sub/email")
    return GoogleIdentity(
        sub=sub,
        email=email.strip().lower(),        # match the lowercased unique index
        # Strict: only a real boolean True passes (avoids bool("false") == True).
        email_verified=claims.get("email_verified") is True,
        name=claims.get("name"),
    )
```

`verify_oauth2_token` verifies the RS256 signature against Google's published certs, the audience (`aud == GOOGLE_CLIENT_ID`), expiry, **and the issuer** (raising `GoogleAuthError` on a bad `iss`). We map its `ValueError`/`GoogleAuthError` to `InvalidGoogleToken` (→ 401) and a `TransportError` (can't reach Google) to `GoogleVerifyUnavailable` (→ 503); the `TransportError` clause must precede the `GoogleAuthError` one since it's a subclass. The issuer re-check is defensive (older library versions). The function does **not** enforce `email_verified` — the route decides.

### `_generate_username(db, email, name)` — in `auth_routes.py` (needs DB)

- Seed: email local part (`email.split("@", 1)[0]`); if it sanitizes to empty, fall back to `name`, then the literal `"pigeon"`.
- Sanitize: drop anything outside `[a-zA-Z0-9_]`, lowercase, clamp to 30 chars; if under 3 chars, pad (e.g. append `"pigeon"`) and re-clamp.
- Uniqueness: if the candidate already exists (case-insensitive, against `ux_users_username_lower`), append `1`, `2`, … keeping the result ≤ 30 by trimming the base to `30 - len(str(n))` before adding the suffix, until free.
- The unique index is the backstop; on the rare race where a concurrently-created row takes the chosen handle, the `flush()` in the route raises `IntegrityError` and the request fails loudly (single-process dev makes this effectively impossible).

The result always satisfies the existing `USERNAME_PATTERN` (`^[a-zA-Z0-9_]{3,30}$`).

### `POST /auth/google` — in `auth_routes.py`

Request body `GoogleLoginIn{ id_token: str }`; response `TokenPairOut` (access + refresh), `Cache-Control: no-store` via `_issue_token_pair`.

1. `identity = verify_google_id_token(payload.id_token)` — imported as `from app.google_auth import verify_google_id_token, InvalidGoogleToken, GoogleVerifyUnavailable` (import the **function**, so tests can monkeypatch `app.auth_routes.verify_google_id_token`):
   - `InvalidGoogleToken` → `_credentials_error()` (**401**, uniform).
   - `GoogleVerifyUnavailable` → **503** (couldn't reach Google — not the client's fault).
   - `RuntimeError` (missing `GOOGLE_CLIENT_ID`) → **500** with a clear detail.
2. If `not identity.email_verified` → **401** (don't create/link on an unverified email).
3. Resolve the user, in order:
   1. **By `google_sub == identity.sub`** → existing Google user.
   2. **Else by `lower(email) == identity.email`** → existing account. If its `google_sub` is null, **link** (set `user.google_sub = identity.sub`). If it already holds a *different* `google_sub`, that's an unexpected conflict (Google email↔account is 1:1, so this only arises from inconsistent data) → **401**, do not overwrite.
   3. **Else create**: `User(username=_generate_username(...), email=identity.email, password_hash=None, google_sub=identity.sub, created_at=utcnow())`; `db.add(user)`.
4. `db.flush()` (assign `user.id` for new users; trip unique backstops), then `return _issue_token_pair(db, user, response)` (which commits). Wrap the flush in `try/except IntegrityError`: on the rare concurrent race (two first-logins with the same `sub`, or a username taken between generation and insert) → `db.rollback()` and re-resolve by `google_sub` once; if a row now exists use it, otherwise raise **409**. Mirrors `register()`'s IntegrityError handling.

Matching is by the stable `sub`; a changed Google email is not propagated to the stored row (out of scope).

### Schema (`app/schemas.py`)

Add:

```python
class GoogleLoginIn(BaseModel):
    id_token: str = Field(min_length=1)
```

Reuse `TokenPairOut` and `UserOut` unchanged.

### Testing

- **Route tests** (`tests/test_auth_api.py` or a new `tests/test_google_auth_api.py`) monkeypatch the seam `app.auth_routes.verify_google_id_token` to return a crafted `GoogleIdentity` — no network. Cases:
  - New Google user → account created with a generated username, `password_hash` is null, `google_sub` set; the returned access token works against `GET /auth/me`.
  - Returning Google user (same `sub`) → logs in, no duplicate account (user count unchanged).
  - Link by verified email → pre-existing password account with email X; Google login with `sub` + email X attaches `google_sub` to the same user id; afterwards both password login and Google login resolve to that user.
  - `email_verified=false` → 401, no account created.
  - Verified email already linked to a *different* `google_sub` → 401, the existing `google_sub` is unchanged (no overwrite).
  - Seam raises `InvalidGoogleToken` → 401.
  - Seam raises `GoogleVerifyUnavailable` → 503.
  - Username collision → two Google users whose emails share a base get distinct handles (`alex`, `alex1`).
- **Seam tests** (`tests/test_google_auth.py`) monkeypatch the underlying `google_id_token.verify_oauth2_token` to return claim dicts (or raise) → assert: a library `ValueError` and a `GoogleAuthError` (wrong issuer) both become `InvalidGoogleToken`; a `TransportError` becomes `GoogleVerifyUnavailable`; the defensive issuer check rejects a bad `iss`; missing `sub`/`email` → `InvalidGoogleToken`; email is lowercased; `email_verified` is strict (a non-boolean truthy like the string `"false"`/`"true"` or `1` does **not** count as verified — only boolean `True`); missing `GOOGLE_CLIENT_ID` → `RuntimeError`.
- **Username helper** unit-tested directly (sanitize, pad short seeds, collision suffixing).

### Docs

- **README** "API at a glance": add `POST /auth/google` — `{id_token}` → token pair (creates or links a Google account). Document the `GOOGLE_CLIENT_ID` env var and the new dependencies.
- **CLAUDE.md**: move Google OAuth out of "still to come" (frontend remains); add gotchas: the endpoint requires `GOOGLE_CLIENT_ID` (else 500); verification lives behind the `verify_google_id_token` seam (tests monkeypatch it); auto-link-by-verified-email trusts the Google side.

## Security caveat

Auto-linking trusts Google's `email_verified` claim, which is sound. But the **password** registration path does not verify email ownership, so a pre-existing (unverified) password account squatting on someone's email would be linked to that person's first Google sign-in. Acceptable at this learning stage; tightening password-side email verification is a future hardening and is recorded here intentionally.

## Risks / notes

- `google-auth`'s `verify_oauth2_token` performs network I/O to fetch Google's certs **on every call** (the reused transport pools connections but does not cache certs; a CacheControl-wrapped session is a future optimization). Tests never touch the network because they monkeypatch the seam (route tests) or the library call (seam tests).
- No migration: additive endpoint + module only. The dev SQLite DB needs no reset for this milestone.
