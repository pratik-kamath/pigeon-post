# Google OAuth (verify ID token) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Sign in with Google" — a `POST /auth/google` endpoint that verifies a Google ID token, resolves or creates the matching user (auto-generating a username, linking by verified email), and returns our own access+refresh token pair.

**Architecture:** Google ID-token verification is isolated in a new `app/google_auth.py` seam (no DB), mirroring how `security.py` holds auth primitives. The route in `auth_routes.py` orchestrates verify → resolve/create/link → `_issue_token_pair`. No model or schema migration — `User.google_sub` (unique, nullable) and a nullable `password_hash` already exist.

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy 2.0 · SQLite · pytest · `google-auth` (+ `requests` transport).

**Spec:** `docs/superpowers/specs/2026-06-14-google-oauth-design.md`

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `backend/requirements.txt` | Modify | Add `google-auth` + `requests`. |
| `backend/app/google_auth.py` | Create | Verify a Google ID token → `GoogleIdentity`; no DB. Maps library errors to `InvalidGoogleToken` / `GoogleVerifyUnavailable`. |
| `backend/app/auth_routes.py` | Modify | `_generate_username` helper, `_resolve_google_user` helper, and the `POST /auth/google` route. |
| `backend/app/schemas.py` | Modify | Add `GoogleLoginIn`. |
| `backend/tests/test_google_auth.py` | Create | Unit tests for the verification seam (monkeypatch the google-auth call). |
| `backend/tests/test_username.py` | Create | Unit tests for `_generate_username`. |
| `backend/tests/test_google_auth_api.py` | Create | Route tests for `POST /auth/google` (monkeypatch the seam). |
| `README.md` (repo root) | Modify | Document the endpoint + `GOOGLE_CLIENT_ID`. |
| `CLAUDE.md` (repo root) | Modify | Status + gotchas. |

Each task ends green and committed. Tasks are ordered by dependency: deps → seam → username helper → route → docs.

---

## Task 1: Add Google auth dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add the dependencies**

In `backend/requirements.txt`, add two lines after `email-validator`:

```
google-auth
requests
```

- [ ] **Step 2: Install into the existing venv**

Run: `cd backend && .venv/bin/pip install -r requirements.txt`
Expected: installs `google-auth`, `requests` (and their deps) successfully.

- [ ] **Step 3: Verify the imports the seam will use are available**

Run:
```bash
cd backend && .venv/bin/python -c "from google.oauth2 import id_token; from google.auth.transport import requests as r; from google.auth import exceptions; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 4: Confirm the existing suite still passes**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: PASS (89 tests; nothing imports the new libs yet).

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt
git commit -m "build: add google-auth + requests for Google OAuth

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

(The installed packages live in the gitignored `.venv`; only `requirements.txt` is committed.)

---

## Task 2: Google ID-token verification seam

**Files:**
- Create: `backend/app/google_auth.py`
- Test: `backend/tests/test_google_auth.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_google_auth.py`:

```python
import pytest
from google.auth import exceptions as google_exceptions

from app import google_auth
from app.google_auth import (
    GoogleIdentity,
    GoogleVerifyUnavailable,
    InvalidGoogleToken,
    verify_google_id_token,
)

CLIENT_ID = "test-client-id.apps.googleusercontent.com"


@pytest.fixture(autouse=True)
def _configure_client_id(monkeypatch):
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_ID", CLIENT_ID)


def _claims(**overrides):
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "google-sub-123",
        "email": "Alex@Example.com",
        "email_verified": True,
        "name": "Alex Example",
    }
    claims.update(overrides)
    return claims


def _patch_verify(monkeypatch, result=None, exc=None):
    def fake_verify(token, transport, audience):
        if exc is not None:
            raise exc
        return result
    monkeypatch.setattr(
        google_auth.google_id_token, "verify_oauth2_token", fake_verify
    )


def test_returns_identity_and_lowercases_email(monkeypatch):
    _patch_verify(monkeypatch, result=_claims())
    assert verify_google_id_token("tok") == GoogleIdentity(
        sub="google-sub-123",
        email="alex@example.com",
        email_verified=True,
        name="Alex Example",
    )


def test_missing_client_id_raises_runtime_error(monkeypatch):
    monkeypatch.setattr(google_auth, "GOOGLE_CLIENT_ID", "")
    _patch_verify(monkeypatch, result=_claims())
    with pytest.raises(RuntimeError):
        verify_google_id_token("tok")


def test_value_error_becomes_invalid_token(monkeypatch):
    _patch_verify(monkeypatch, exc=ValueError("bad signature"))
    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token("tok")


def test_google_auth_error_becomes_invalid_token(monkeypatch):
    _patch_verify(monkeypatch, exc=google_exceptions.GoogleAuthError("Wrong issuer."))
    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token("tok")


def test_transport_error_becomes_unavailable(monkeypatch):
    _patch_verify(monkeypatch, exc=google_exceptions.TransportError("network down"))
    with pytest.raises(GoogleVerifyUnavailable):
        verify_google_id_token("tok")


def test_bad_issuer_rejected(monkeypatch):
    _patch_verify(monkeypatch, result=_claims(iss="evil.com"))
    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token("tok")


def test_missing_sub_or_email_rejected(monkeypatch):
    _patch_verify(monkeypatch, result=_claims(sub=None))
    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token("tok")


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None, "True"])
def test_email_verified_is_strict(monkeypatch, value):
    _patch_verify(monkeypatch, result=_claims(email_verified=value))
    assert verify_google_id_token("tok").email_verified is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_google_auth.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.google_auth'`.

- [ ] **Step 3: Create the seam module**

Create `backend/app/google_auth.py`:

```python
"""Google ID token verification. No DB access."""
import os
from dataclasses import dataclass

from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
_ACCEPTED_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
# Reused for HTTP connection pooling. Does NOT cache Google's signing certs —
# verify_oauth2_token re-fetches them each call. Fine for dev.
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
        claims = google_id_token.verify_oauth2_token(
            token, _transport, GOOGLE_CLIENT_ID
        )
    except google_exceptions.TransportError as exc:
        # Subclass of GoogleAuthError — must be caught first.
        raise GoogleVerifyUnavailable(str(exc)) from exc
    except (ValueError, google_exceptions.GoogleAuthError) as exc:
        # ValueError: bad signature/aud/exp/format.
        # GoogleAuthError: wrong issuer (verify_oauth2_token checks iss itself).
        raise InvalidGoogleToken(str(exc)) from exc
    # Defensive (older google-auth versions didn't check iss inside verify):
    if claims.get("iss") not in _ACCEPTED_ISSUERS:
        raise InvalidGoogleToken("untrusted issuer")
    sub, email = claims.get("sub"), claims.get("email")
    if not sub or not email:
        raise InvalidGoogleToken("missing sub/email")
    return GoogleIdentity(
        sub=sub,
        email=email.strip().lower(),  # match the lowercased unique index
        # Strict: only a real boolean True passes (avoids bool("false") == True).
        email_verified=claims.get("email_verified") is True,
        name=claims.get("name"),
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_google_auth.py -q`
Expected: PASS (all cases including the parametrized strict-`email_verified` ones).

- [ ] **Step 5: Commit**

```bash
git add backend/app/google_auth.py backend/tests/test_google_auth.py
git commit -m "feat: Google ID token verification seam

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Username generator

**Files:**
- Modify: `backend/app/auth_routes.py`
- Test: `backend/tests/test_username.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_username.py`:

```python
from datetime import datetime

from app.auth_routes import _generate_username
from app.models import User


def _seed(db_session, username):
    db_session.add(User(
        username=username, email=f"{username}@example.com",
        password_hash="x", created_at=datetime(2026, 6, 14),
    ))
    db_session.commit()


def test_generates_from_email_local_part(db_session):
    assert _generate_username(db_session, "alex@example.com", "Alex") == "alex"


def test_sanitizes_disallowed_chars(db_session):
    assert _generate_username(db_session, "a.l-e+x@example.com", None) == "alex"


def test_collision_appends_suffix(db_session):
    _seed(db_session, "alex")
    assert _generate_username(db_session, "alex@example.com", None) == "alex1"


def test_second_collision_increments(db_session):
    _seed(db_session, "alex")
    _seed(db_session, "alex1")
    assert _generate_username(db_session, "alex@example.com", None) == "alex2"


def test_short_seed_is_padded(db_session):
    result = _generate_username(db_session, "ab@example.com", None)
    assert len(result) >= 3 and result.startswith("ab")


def test_falls_back_to_name_when_seed_too_short(db_session):
    assert _generate_username(db_session, "a@example.com", "Bob") == "bob"


def test_empty_seed_falls_back_to_pigeon(db_session):
    # non-ASCII local part sanitizes to empty, no usable name
    assert _generate_username(db_session, "区@example.com", None) == "pigeon"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_username.py -q`
Expected: FAIL — `ImportError: cannot import name '_generate_username' from 'app.auth_routes'`.

- [ ] **Step 3: Implement the helper**

In `backend/app/auth_routes.py`, add `import re` at the top of the imports (with the stdlib imports), then add this function (e.g. just below `_credentials_error`):

```python
def _generate_username(db: Session, email: str, name: str | None) -> str:
    """A unique username seeded from the Google email/name.

    Always satisfies USERNAME_PATTERN (^[a-zA-Z0-9_]{3,30}$): sanitized to
    allowed chars, padded if too short, and suffixed on collision.
    """
    base = re.sub(r"[^a-zA-Z0-9_]", "", email.split("@", 1)[0]).lower()
    if len(base) < 3 and name:
        base = re.sub(r"[^a-zA-Z0-9_]", "", name).lower()
    if len(base) < 3:
        base = base + "pigeon"
    base = base[:30]

    candidate = base
    n = 0
    while db.execute(
        select(models.User.id).where(
            func.lower(models.User.username) == candidate.lower()
        )
    ).first() is not None:
        n += 1
        suffix = str(n)
        candidate = f"{base[:30 - len(suffix)]}{suffix}"
    return candidate
```

(`select`, `func`, `models`, and `Session` are already imported in this file.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_username.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/auth_routes.py backend/tests/test_username.py
git commit -m "feat: unique username generator for Google sign-ups

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: POST /auth/google endpoint

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/auth_routes.py`
- Test: `backend/tests/test_google_auth_api.py`

- [ ] **Step 1: Write the failing route tests**

Create `backend/tests/test_google_auth_api.py`:

```python
from app import auth_routes
from app.google_auth import GoogleIdentity, GoogleVerifyUnavailable, InvalidGoogleToken
from app.models import User


def patch_identity(monkeypatch, *, sub="sub-123", email="alex@example.com",
                   email_verified=True, name="Alex Example"):
    identity = GoogleIdentity(sub=sub, email=email,
                              email_verified=email_verified, name=name)
    monkeypatch.setattr(auth_routes, "verify_google_id_token", lambda token: identity)
    return identity


def patch_raises(monkeypatch, exc):
    def boom(token):
        raise exc
    monkeypatch.setattr(auth_routes, "verify_google_id_token", boom)


def google_login(client, id_token="tok"):
    return client.post("/auth/google", json={"id_token": id_token})


def test_new_user_created_and_logged_in(client, monkeypatch, db_session):
    patch_identity(monkeypatch, sub="sub-new", email="newbie@example.com", name="New Bie")
    resp = google_login(client)
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    assert tokens["access_token"] and tokens["refresh_token"]
    me = client.get("/auth/me",
                    headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "newbie@example.com"
    assert me.json()["username"]  # auto-generated, non-empty
    created = db_session.query(User).filter(User.email == "newbie@example.com").one()
    assert created.password_hash is None     # Google-only account, no password
    assert created.google_sub == "sub-new"


def test_returning_user_no_duplicate(client, monkeypatch, db_session):
    patch_identity(monkeypatch, sub="sub-xyz", email="rep@example.com")
    google_login(client)
    google_login(client)
    assert db_session.query(User).filter(User.google_sub == "sub-xyz").count() == 1


def test_links_to_existing_password_account(client, monkeypatch, db_session):
    reg = client.post("/auth/register", json={
        "username": "alex", "email": "alex@example.com", "password": "password123",
    })
    assert reg.status_code == 201
    patch_identity(monkeypatch, sub="sub-link", email="alex@example.com")
    assert google_login(client).status_code == 200
    user = db_session.query(User).filter(User.email == "alex@example.com").one()
    assert user.google_sub == "sub-link"
    assert db_session.query(User).count() == 1


def test_unverified_email_rejected(client, monkeypatch, db_session):
    patch_identity(monkeypatch, email="x@example.com", email_verified=False)
    assert google_login(client).status_code == 401
    assert db_session.query(User).count() == 0


def test_different_google_sub_same_email_conflict(client, monkeypatch, db_session):
    patch_identity(monkeypatch, sub="sub-A", email="dup@example.com")
    google_login(client)
    patch_identity(monkeypatch, sub="sub-B", email="dup@example.com")
    assert google_login(client).status_code == 401
    user = db_session.query(User).filter(User.email == "dup@example.com").one()
    assert user.google_sub == "sub-A"  # unchanged, not overwritten


def test_invalid_token_401(client, monkeypatch):
    patch_raises(monkeypatch, InvalidGoogleToken("bad"))
    assert google_login(client).status_code == 401


def test_unavailable_503(client, monkeypatch):
    patch_raises(monkeypatch, GoogleVerifyUnavailable("network"))
    assert google_login(client).status_code == 503


def test_blank_id_token_422(client):
    assert client.post("/auth/google", json={"id_token": ""}).status_code == 422


def test_username_collision_distinct_handles(client, monkeypatch, db_session):
    patch_identity(monkeypatch, sub="sub-1", email="sam@example.com")
    google_login(client)
    patch_identity(monkeypatch, sub="sub-2", email="sam@other.com")
    google_login(client)
    names = {u.username for u in db_session.query(User).all()}
    assert "sam" in names and "sam1" in names
```

- [ ] **Step 2: Run the route tests to verify they fail**

Run: `cd backend && .venv/bin/python -m pytest tests/test_google_auth_api.py -q`
Expected: FAIL — `404` on `POST /auth/google` (route not defined) / `ImportError` for `GoogleLoginIn` once wired. Confirm failures are behavioral, not collection errors.

- [ ] **Step 3: Add the request schema**

In `backend/app/schemas.py`, add (near the other auth schemas, after `RefreshIn`):

```python
class GoogleLoginIn(BaseModel):
    id_token: str = Field(min_length=1)
```

(`BaseModel` and `Field` are already imported.)

- [ ] **Step 4: Wire imports in `auth_routes.py`**

In `backend/app/auth_routes.py`:
- Add the seam import (import the **functions/classes**, so the route tests' `monkeypatch.setattr(auth_routes, "verify_google_id_token", ...)` works):

```python
from app.google_auth import (
    GoogleVerifyUnavailable,
    InvalidGoogleToken,
    verify_google_id_token,
)
```

- Add `GoogleLoginIn` to the existing `from app.schemas import ...` line.

- [ ] **Step 5: Add the resolve helper and the route**

In `backend/app/auth_routes.py`, add the helper (below `_generate_username`):

```python
def _resolve_google_user(db: Session, identity) -> models.User:
    """Find by google_sub, else link by verified email, else create."""
    user = db.execute(
        select(models.User).where(models.User.google_sub == identity.sub)
    ).scalar_one_or_none()
    if user is not None:
        return user

    existing = db.execute(
        select(models.User).where(
            func.lower(models.User.email) == identity.email
        )
    ).scalar_one_or_none()
    if existing is not None:
        # google_sub == identity.sub would have matched above, so a set value
        # here is a *different* Google account on the same email — refuse it.
        if existing.google_sub is not None:
            raise _credentials_error()
        existing.google_sub = identity.sub
        return existing

    user = models.User(
        username=_generate_username(db, identity.email, identity.name),
        email=identity.email,
        password_hash=None,
        google_sub=identity.sub,
        created_at=utcnow(),
    )
    db.add(user)
    return user
```

Then add the route (place it with the other auth routes):

```python
@router.post("/google", response_model=TokenPairOut)
def google_login(
    payload: GoogleLoginIn, response: Response, db: Session = Depends(get_db)
):
    try:
        identity = verify_google_id_token(payload.id_token)
    except InvalidGoogleToken:
        raise _credentials_error()
    except GoogleVerifyUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="google verification unavailable"
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500, detail="google login not configured"
        ) from exc
    if not identity.email_verified:
        raise _credentials_error()

    user = _resolve_google_user(db, identity)
    try:
        db.flush()
    except IntegrityError:
        # Rare concurrent race (same sub created, or username taken between
        # generation and insert). Re-resolve by the stable sub; if still
        # nothing, give up with a clear conflict.
        db.rollback()
        user = db.execute(
            select(models.User).where(models.User.google_sub == identity.sub)
        ).scalar_one_or_none()
        if user is None:
            raise HTTPException(
                status_code=409, detail="could not complete google login"
            )
    return _issue_token_pair(db, user, response)
```

(`Response`, `HTTPException`, `IntegrityError`, `select`, `func`, `utcnow`, `_issue_token_pair`, `_credentials_error`, `TokenPairOut` are all already imported/defined in this file.)

- [ ] **Step 6: Run the route tests to verify they pass**

Run: `cd backend && .venv/bin/python -m pytest tests/test_google_auth_api.py -q`
Expected: PASS.

- [ ] **Step 7: Run the whole suite**

Run: `cd backend && .venv/bin/python -m pytest -q`
Expected: PASS (existing 89 + seam + username + route tests).

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas.py backend/app/auth_routes.py backend/tests/test_google_auth_api.py
git commit -m "feat: POST /auth/google (verify ID token, link-or-create user)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Documentation

**Files:**
- Modify: `README.md` (repo root)
- Modify: `CLAUDE.md` (repo root)

> Both files are at the **repo root**. Run the commit from the repo root.

- [ ] **Step 1: README — add the endpoint**

In `README.md` "API at a glance", add this line right after the `POST /auth/login` bullet:

```markdown
- `POST /auth/google` — `{id_token}` (a Google ID token) → token pair; creates a new account or links to an existing one by verified email. Needs `GOOGLE_CLIENT_ID` set.
```

- [ ] **Step 2: README — document the env var**

In `README.md`, find the line:

```
Set `JWT_SECRET` in real deployments; a dev default is baked in. Access tokens
last 15 minutes — use `/auth/refresh` to stay logged in.
```

Append a sentence so it reads:

```
Set `JWT_SECRET` in real deployments; a dev default is baked in. Access tokens
last 15 minutes — use `/auth/refresh` to stay logged in. Set `GOOGLE_CLIENT_ID`
(your Google OAuth client ID) to enable `POST /auth/google`.
```

- [ ] **Step 3: CLAUDE.md — update status**

In `CLAUDE.md` intro, find:

```
Messages are now tied to user accounts (sent by the authenticated user, addressed to a registered username). Still to come: Google OAuth and the frontend.
```

Replace with:

```
Messages are tied to user accounts, and Google sign-in is implemented (`POST /auth/google`, verify-ID-token flow). Still to come: the frontend.
```

- [ ] **Step 4: CLAUDE.md — add a gotcha**

In `CLAUDE.md` under `## Gotchas`, append:

```markdown
- `POST /auth/google` verifies a Google ID token (no redirect flow) and needs `GOOGLE_CLIENT_ID` set, else it returns 500. Verification is isolated in `app/google_auth.py` behind `verify_google_id_token` — tests monkeypatch that seam (and patch `app.auth_routes.verify_google_id_token` for route tests). A Google login auto-links to an existing account by verified email; password-side emails aren't verified, a documented trust tradeoff.
```

- [ ] **Step 5: Commit** (from the repo root)

```bash
git add README.md CLAUDE.md
git commit -m "docs: document Google OAuth endpoint and config

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] `cd backend && .venv/bin/python -m pytest -q` → all green.
- [ ] `git log --oneline` shows five feature commits (deps, seam, username, route, docs) on `feat/google-oauth`.
- [ ] Optional manual smoke (needs a real `GOOGLE_CLIENT_ID` and a real Google ID token, so usually skipped in dev): `GOOGLE_CLIENT_ID=... uvicorn app.main:app` then `POST /auth/google`. The automated tests are the source of truth.
- [ ] Hand off via `superpowers:finishing-a-development-branch`.
