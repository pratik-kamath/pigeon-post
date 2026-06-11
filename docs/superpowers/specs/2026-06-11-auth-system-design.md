# Auth System Design

**Date:** 2026-06-11
**Status:** Approved (pending final user review)
**Scope:** Phase 1 auth — email/password + Google sign-in, JWT access/refresh pair, messages tied to user accounts.

## Goal

Replace the free-text `sender`/`recipient` strings on messages with real user accounts. Users can register with email/password or sign in with Google; either path yields the same backend-issued token pair. Message endpoints become ownership-aware: you send as yourself and read only your own mail.

## Stack decision

- **Authlib** handles the Google OAuth/OIDC flow (consent redirect, `state`, code exchange, ID-token verification). Hand-rolling OIDC is the highest-risk, lowest-learning-per-line part of auth — delegated.
- **Hand-rolled** (the learning core): password hashing with `argon2-cffi`, access-token JWTs with `PyJWT`, refresh-token issuance/rotation/revocation.
- **Rejected:** fully hand-rolled OAuth (security footguns), `fastapi-users` (too much magic for a learning codebase).

New runtime deps: `authlib`, `pyjwt`, `argon2-cffi`, `itsdangerous` (SessionMiddleware), `email-validator` (Pydantic `EmailStr`).

## Data model

### `users`

| Column | Notes |
|---|---|
| `id` | PK |
| `username` | Non-null; display case preserved; **case-insensitive unique** via functional index on `lower(username)`. Restricted to `^[a-zA-Z0-9_]{3,30}$` (ASCII-only, so SQLite's ASCII-only `lower()` is sufficient). Messages are addressed to usernames. |
| `email` | Non-null; validated with Pydantic `EmailStr`; case-insensitive unique via functional index on `lower(email)`. |
| `password_hash` | Nullable — null for Google-only accounts. Full argon2 encoded hash. |
| `google_sub` | Nullable, unique, `String(255)`. Google's stable subject ID — login matches on `sub`, never on email. |
| `created_at` | Naive UTC, matching the existing codebase convention. |

Inputs are normalized (`strip`, lowercase for comparison) before insert and on every uniqueness lookup (`func.lower(...)` on both sides).

Deliberately omitted as YAGNI for now: `email_verified_at` (only needed for email-based account linking, which is deferred), `updated_at`.

### `refresh_tokens`

| Column | Notes |
|---|---|
| `id` | PK |
| `user_id` | FK → users, indexed |
| `token_hash` | Hex SHA-256 (`String(64)`) of the opaque random token; **unique indexed**. Raw token is never stored. |
| `expires_at` | Naive UTC |
| `created_at` | Naive UTC |
| `revoked_at` | Nullable; set on logout, rotation, and reuse-detection sweep |

Refresh tokens are opaque random strings, not JWTs — they hit the DB anyway, so statelessness buys nothing and revocation stays trivial.

### `messages` (changed)

`sender`/`recipient` string columns become `sender_id`/`recipient_id` FKs to `users`. Dev-only SQLite: drop and recreate the DB, no migration tooling (Alembic can be its own later milestone). API responses join back to usernames; raw IDs are not exposed.

- **FK enforcement:** SQLite ignores FKs unless `PRAGMA foreign_keys=ON` — added to the existing connection event listener in `db.py` (which currently only sets WAL).
- **Index swap:** the string-era indexes are replaced with `(status, arrival_at)` for the scheduler sweep, `(sender_id, sent_at)` for sent mail, and `(recipient_id, status, sent_at)` for the inbox.

## Token semantics

- **Access token:** JWT, ~15 min TTL, HS256 with `JWT_SECRET`. Claims: `sub` (encoded as `str(user.id)`, parsed back to int — PyJWT requires a string `sub`), `exp`, `iat`, `iss`. Decoded with `algorithms=["HS256"]` and required-claims enforcement. Signature/expiry validation is stateless; guarded endpoints still load the user row.
- **Refresh token:** opaque, generated with `secrets.token_urlsafe(32)`, ~30 day TTL, DB-backed, **rotated on every use**. Rotation is atomic: `UPDATE refresh_tokens SET revoked_at = :now WHERE id = :id AND revoked_at IS NULL AND expires_at > :now`; only if rowcount == 1 is the replacement inserted.
- **Reuse detection (cheap version):** presenting a revoked refresh token revokes *all* of that user's refresh tokens and returns 401 — re-login required. No token-family table.

## Account linking rule

- Google ID tokens with `email_verified` not true are **rejected** (400) — unverified provider emails must not create accounts or trigger collision logic.
- Google sign-in matches on `google_sub` only.
- No match + unknown email → create a new user (username derived from the email local part, uniquified).
- No match + email already belongs to an existing account → **409, "an account with this email already exists — log in with the existing method."** (Provider-neutral wording: the existing account might not be a password account.) No silent linking (account-takeover vector while local emails are unverified). Explicit linking from account settings is a deferred milestone.

## Endpoints

### New router `app/auth_routes.py` (`/auth`)

| Endpoint | Behavior |
|---|---|
| `POST /auth/register` | `{username, email, password}` → create user, return token pair. 409 on duplicate username/email (case-insensitive). |
| `POST /auth/login` | `{email, password}` → verify (then `check_needs_rehash`), return token pair. Generic 401 for unknown email *or* wrong password — no account enumeration. |
| `POST /auth/refresh` | `{refresh_token}` → atomic rotation, new pair. Replayed-revoked token trips reuse detection. |
| `POST /auth/logout` | Revokes the presented refresh token. Always 204 — idempotent, never confirms whether a token existed. Access token expires naturally. |
| `GET /auth/google/login` | Authlib builds the Google consent redirect. |
| `GET /auth/google/callback` | Code exchange + ID-token verification via Authlib, then the linking rule above. |
| `GET /auth/me` | Current user — the simplest guard smoke test in `/docs`. |

Token pair response shape (login/register/refresh/callback): `{access_token, refresh_token, token_type: "bearer"}` in the JSON body, always with `Cache-Control: no-store`. The Google callback returning JSON to a browser redirect is a **temporary dev/docs shape** — before the React frontend it becomes set-cookie-then-redirect or a frontend code-exchange flow.

Password hashing/verification endpoints are plain `def` routes (FastAPI runs them in the threadpool) so argon2 work never blocks the event loop.

### The guard

`get_current_user` FastAPI dependency: reads `Authorization: Bearer <jwt>`, decodes with PyJWT (fixed algorithm list, required claims), loads the user, 401 with `WWW-Authenticate: Bearer` on any failure. Endpoints opt in; nothing global.

### Messages router (changed contract)

- `POST /messages` — auth required. Body: `{recipient_username, body, origin, destination}`. Sender = current user. 404 if recipient doesn't exist.
- `GET /messages/sent` — current user's sent messages, any status (replaces `?sender=`).
- `GET /messages/inbox` — current user's delivered messages (replaces `?recipient=`).
- `GET /messages/{id}` — sender always; recipient only once delivered (no peeking mid-flight); anyone else gets 404, not 403 — don't confirm existence.
- **Route ordering:** `/messages/sent` and `/messages/inbox` are declared *before* `/messages/{id}`, or FastAPI routes "sent" into the dynamic path and returns a confusing 422.
- **Response schema:** `{id, sender_username, recipient_username, body, origin, destination, distance_km, status, sent_at, arrival_at, resolved_at}` — usernames joined from `users`, raw IDs not exposed.

## Configuration

Env vars with dev-friendly defaults so tests run with zero setup: `JWT_SECRET`, `SESSION_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`. `SessionMiddleware` is added in `create_app()` — Authlib needs it to stash OAuth `state` in a signed cookie during the redirect dance; nothing else uses the session.

## Error handling

- 401 (uniform message, `WWW-Authenticate: Bearer`): missing/expired/malformed access token, bad credentials, revoked/unknown refresh token on `/auth/refresh` (logout instead returns 204 unconditionally — idempotent, no token-existence oracle).
- 409: registration conflicts; Google email collision with an existing password account.
- 404: unknown recipient on send; messages you're not a party to.
- 400: OAuth callback failures (denied consent, bad state, provider error) — plain message, no stack traces.
- Reuse detection logs a warning with the user id, matching the delivery sweep's logging style.

## Testing

TDD throughout. Google is never called in tests.

- **Unit:** argon2 hash/verify round-trip; JWT encode/decode (expiry, wrong secret, missing claims); refresh rotation incl. replay → revoke-all.
- **API:** register/login/refresh/logout happy + failure paths; guard rejection cases; message ownership rules (sender vs recipient vs stranger, in-flight vs delivered visibility).
- **OAuth:** `monkeypatch` Authlib's `authorize_access_token` to exercise the three callback branches (known sub / new user / email collision). Redirect endpoint gets a returns-a-Google-URL smoke test.
- Existing message tests updated for the new contract; `conftest.py` grows a logged-in-user fixture.

## Milestones (implemented one at a time)

1. **Users + password auth + JWT pair** — User/RefreshToken models, register/login/refresh/logout/me, the guard. Messages untouched.
2. **Messages tied to users** — FK switch (drop/recreate dev DB), new message contract, ownership rules.
3. **Google OAuth** — Authlib wiring, callback branches, session middleware.

Each milestone lands green before the next starts.

## External review

Critiqued by Codex (2026-06-11, two rounds).

Round 1 — adopted: ownership-aware message API, refresh-token unique index + atomic rotation + cheap reuse detection, full JWT claim set, `check_needs_rehash`. Rejected/adjusted: email-based auto-linking (replaced with 409-on-collision — Codex's "create a new account" alternative contradicted the unique email constraint), `*_normalized` columns (functional indexes instead), `email_verified_at`/`updated_at`/`revoked_reason` (YAGNI until the linking milestone).

Round 2 — all points adopted: `email_verified` requirement on Google ID tokens, provider-neutral collision message, `Cache-Control: no-store` + callback-JSON-is-temporary note, username pattern + normalization rules, `email-validator` dep, `PRAGMA foreign_keys=ON` (verified missing in `db.py`), explicit message response schema, route-ordering note, FK index swap, expiry in the atomic rotation condition, token entropy/storage spec, string JWT `sub`, sync `def` routes for argon2.
