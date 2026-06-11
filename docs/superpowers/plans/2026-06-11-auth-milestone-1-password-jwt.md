# Auth Milestone 1: Users + Password Auth + JWT Pair — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users can register with email/password, log in, refresh/rotate tokens, log out, and call a guarded `/auth/me` — messages are untouched (milestone 2).

**Architecture:** Two new tables (`users`, `refresh_tokens`) in the existing `app/models.py`; a pure-primitives `app/security.py` (argon2, PyJWT, refresh-token generation — no DB); an `app/auth_routes.py` router holding endpoints, the `get_current_user` guard, and rotation logic. Spec: `docs/superpowers/specs/2026-06-11-auth-system-design.md`.

**Tech Stack:** FastAPI, SQLAlchemy 2.x, SQLite, `pyjwt`, `argon2-cffi`, `email-validator` (Pydantic `EmailStr`).

**Conventions (from spec + codebase):**
- Naive UTC everywhere — always `from app.delivery import utcnow`, never `datetime.now()`.
- All auth routes are sync `def` (threadpool), matching the existing routers and keeping argon2 off the event loop.
- Auth failures are a uniform 401 `{"detail": "invalid credentials"}` with `WWW-Authenticate: Bearer`.
- Token-pair responses always set `Cache-Control: no-store`.
- All commands run from `backend/` with `.venv` active.

---

### Task 1: Swap speculative auth deps for the chosen stack

`requirements.txt` contains `passlib[bcrypt]`, `python-jose[cryptography]`, `python-multipart` — added speculatively, used nowhere (verify: `grep -r "passlib\|jose\|multipart" app/ tests/` returns nothing). The spec chose `pyjwt` + `argon2-cffi`, and all bodies are JSON (no form parsing needed).

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Replace requirements.txt contents**

```text
fastapi
uvicorn[standard]
sqlalchemy
apscheduler<4
pyjwt
argon2-cffi
email-validator
```

- [ ] **Step 2: Install and verify existing tests still pass**

Run: `pip install -r requirements-dev.txt && pytest`
Expected: install succeeds; all existing tests PASS.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: swap speculative auth deps for pyjwt + argon2-cffi + email-validator"
```

---

### Task 2: Password hashing primitives

**Files:**
- Create: `backend/app/security.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_security.py
from app import security


class TestPasswordHashing:
    def test_hash_verify_round_trip(self):
        h = security.hash_password("correct horse battery staple")
        assert h != "correct horse battery staple"
        assert h.startswith("$argon2")
        assert security.verify_password("correct horse battery staple", h)

    def test_wrong_password_fails(self):
        h = security.hash_password("right")
        assert not security.verify_password("wrong", h)

    def test_fresh_hash_needs_no_rehash(self):
        h = security.hash_password("pw")
        assert not security.password_needs_rehash(h)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_security.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.security'`

- [ ] **Step 3: Write the implementation**

```python
# backend/app/security.py
"""Auth primitives: password hashing, access JWTs, refresh tokens. No DB access."""
import hashlib
import os
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.delivery import utcnow

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-not-for-production")
JWT_ISSUER = "pigeon-post"
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=30)

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_security.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/test_security.py
git commit -m "feat: argon2 password hashing primitives"
```

---

### Task 3: Access token (JWT) primitives

**Files:**
- Modify: `backend/app/security.py`
- Modify: `backend/tests/test_security.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_security.py`)

```python
from datetime import timedelta

import jwt
import pytest


class TestAccessTokens:
    def test_round_trip_returns_user_id(self):
        token = security.create_access_token(42)
        assert security.decode_access_token(token) == 42

    def test_expired_token_rejected(self):
        token = security.create_access_token(42, ttl=timedelta(seconds=-1))
        with pytest.raises(jwt.ExpiredSignatureError):
            security.decode_access_token(token)

    def test_wrong_secret_rejected(self):
        forged = jwt.encode(
            {"sub": "42", "iat": 0, "exp": 9999999999, "iss": security.JWT_ISSUER},
            "not-the-real-secret",
            algorithm="HS256",
        )
        with pytest.raises(jwt.InvalidSignatureError):
            security.decode_access_token(forged)

    def test_missing_issuer_rejected(self):
        incomplete = jwt.encode(
            {"sub": "42", "iat": 0, "exp": 9999999999},
            security.JWT_SECRET,
            algorithm="HS256",
        )
        with pytest.raises(jwt.MissingRequiredClaimError):
            security.decode_access_token(incomplete)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_security.py -v`
Expected: new tests FAIL — `AttributeError: module 'app.security' has no attribute 'create_access_token'`

- [ ] **Step 3: Write the implementation** (append to `app/security.py`)

```python
def create_access_token(user_id: int, ttl: timedelta = ACCESS_TOKEN_TTL) -> str:
    now = utcnow()
    payload = {
        # PyJWT 2.10+ requires sub to be a string; parsed back to int on decode.
        "sub": str(user_id),
        "iat": now,
        "exp": now + ttl,
        "iss": JWT_ISSUER,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int:
    """Returns the user id. Raises jwt.InvalidTokenError (any subclass) on failure."""
    payload = jwt.decode(
        token,
        JWT_SECRET,
        algorithms=[JWT_ALGORITHM],
        issuer=JWT_ISSUER,
        options={"require": ["sub", "exp", "iat", "iss"]},
    )
    return int(payload["sub"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_security.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/test_security.py
git commit -m "feat: JWT access token create/decode with full claim enforcement"
```

---

### Task 4: Refresh token primitives

**Files:**
- Modify: `backend/app/security.py`
- Modify: `backend/tests/test_security.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_security.py`)

```python
class TestRefreshTokens:
    def test_new_token_returns_raw_and_hash(self):
        raw, token_hash = security.new_refresh_token()
        assert security.hash_refresh_token(raw) == token_hash

    def test_hash_is_hex_sha256(self):
        _, token_hash = security.new_refresh_token()
        assert len(token_hash) == 64
        int(token_hash, 16)  # raises if not hex

    def test_tokens_are_unique(self):
        assert security.new_refresh_token() != security.new_refresh_token()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_security.py -v`
Expected: new tests FAIL — `AttributeError ... no attribute 'new_refresh_token'`

- [ ] **Step 3: Write the implementation** (append to `app/security.py`)

```python
def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the client, sha256 hex hash for the DB)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_security.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/security.py tests/test_security.py
git commit -m "feat: opaque refresh token generation and hashing"
```

---

### Task 5: User and RefreshToken models

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_models.py`; it already imports `db_session` via the conftest fixture)

```python
from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import RefreshToken, User


def _user(**overrides):
    defaults = dict(
        username="alice",
        email="alice@example.com",
        password_hash="$argon2-fake",
        created_at=datetime(2026, 6, 11, 12, 0, 0),
    )
    defaults.update(overrides)
    return User(**defaults)


class TestUserModel:
    def test_create_user(self, db_session):
        db_session.add(_user())
        db_session.commit()
        user = db_session.query(User).one()
        assert user.username == "alice"
        assert user.google_sub is None

    def test_username_unique_case_insensitive(self, db_session):
        db_session.add(_user())
        db_session.commit()
        db_session.add(_user(username="ALICE", email="other@example.com"))
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_email_unique_case_insensitive(self, db_session):
        db_session.add(_user())
        db_session.commit()
        db_session.add(_user(username="bob", email="ALICE@example.com"))
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestRefreshTokenModel:
    def test_token_hash_unique(self, db_session):
        db_session.add(_user())
        db_session.commit()
        user = db_session.query(User).one()
        common = dict(
            user_id=user.id,
            token_hash="a" * 64,
            expires_at=datetime(2026, 7, 11),
            created_at=datetime(2026, 6, 11),
        )
        db_session.add(RefreshToken(**common))
        db_session.commit()
        db_session.add(RefreshToken(**common))
        with pytest.raises(IntegrityError):
            db_session.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'RefreshToken'`

- [ ] **Step 3: Write the implementation** (append to `app/models.py`; extend the existing imports with `ForeignKey` and `text`)

```python
# imports line becomes:
from sqlalchemy import (
    CheckConstraint, DateTime, Float, ForeignKey, Index, String, text,
)
```

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))

    __table_args__ = (
        # Case-insensitive uniqueness; usernames are ASCII-only so SQLite's
        # ASCII-only lower() is sufficient.
        Index("ux_users_username_lower", text("lower(username)"), unique=True),
        Index("ux_users_email_lower", text("lower(email)"), unique=True),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_models.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_models.py
git commit -m "feat: User and RefreshToken models with case-insensitive unique indexes"
```

---

### Task 6: Auth schemas + POST /auth/register

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/auth_routes.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_auth_api.py
REGISTER = {"username": "alice", "email": "alice@example.com", "password": "hunter2hunter2"}


def register(client, **overrides):
    return client.post("/auth/register", json={**REGISTER, **overrides})


class TestRegister:
    def test_register_returns_token_pair(self, client):
        resp = register(client)
        assert resp.status_code == 201
        body = resp.json()
        assert set(body) == {"access_token", "refresh_token", "token_type"}
        assert body["token_type"] == "bearer"
        assert resp.headers["Cache-Control"] == "no-store"

    def test_duplicate_username_409_case_insensitive(self, client):
        register(client)
        resp = register(client, username="ALICE", email="other@example.com")
        assert resp.status_code == 409

    def test_duplicate_email_409_case_insensitive(self, client):
        register(client)
        resp = register(client, username="bob", email="ALICE@example.com")
        assert resp.status_code == 409

    def test_invalid_username_422(self, client):
        assert register(client, username="no spaces!").status_code == 422
        assert register(client, username="ab").status_code == 422

    def test_short_password_422(self, client):
        assert register(client, password="short").status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth_api.py -v`
Expected: FAIL — 404s (no `/auth/register` route yet)

- [ ] **Step 3: Add schemas** (append to `app/schemas.py`; add `import re` at top and `EmailStr` to the pydantic import)

```python
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,30}$")


class RegisterIn(BaseModel):
    username: str
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)

    @field_validator("username")
    @classmethod
    def valid_username(cls, value: str) -> str:
        value = value.strip()
        if not USERNAME_PATTERN.fullmatch(value):
            raise ValueError(
                "username must be 3-30 characters: letters, digits, underscore"
            )
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        # Stored lowercase so plain equality works everywhere downstream.
        return value.strip().lower()


class LoginIn(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: str
    created_at: datetime
```

- [ ] **Step 4: Create the auth router with register**

```python
# backend/app/auth_routes.py
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, security
from app.db import get_db
from app.delivery import utcnow
from app.schemas import RegisterIn, TokenPairOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _credentials_error() -> HTTPException:
    # One uniform 401 for every auth failure — no account enumeration.
    return HTTPException(
        status_code=401,
        detail="invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _issue_token_pair(
    db: Session, user: models.User, response: Response
) -> TokenPairOut:
    now = utcnow()
    raw, token_hash = security.new_refresh_token()
    db.add(
        models.RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + security.REFRESH_TOKEN_TTL,
            created_at=now,
        )
    )
    db.commit()
    response.headers["Cache-Control"] = "no-store"
    return TokenPairOut(
        access_token=security.create_access_token(user.id),
        refresh_token=raw,
    )


@router.post("/register", response_model=TokenPairOut, status_code=201)
def register(payload: RegisterIn, response: Response, db: Session = Depends(get_db)):
    taken = db.execute(
        select(models.User.id).where(
            (func.lower(models.User.username) == payload.username.lower())
            | (models.User.email == payload.email)  # email is stored lowercase
        )
    ).first()
    if taken:
        raise HTTPException(status_code=409, detail="username or email already taken")
    user = models.User(
        username=payload.username,
        email=payload.email,
        password_hash=security.hash_password(payload.password),
        created_at=utcnow(),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Unique-index backstop for races the pre-check missed.
        db.rollback()
        raise HTTPException(status_code=409, detail="username or email already taken")
    db.refresh(user)
    return _issue_token_pair(db, user, response)
```

- [ ] **Step 5: Wire the router** (in `app/main.py`)

```python
# import line additions:
from app.auth_routes import router as auth_router
# after app.include_router(router):
app.include_router(auth_router)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_auth_api.py -v`
Expected: 5 PASS

- [ ] **Step 7: Run the full suite, then commit**

Run: `pytest`
Expected: all PASS

```bash
git add app/schemas.py app/auth_routes.py app/main.py tests/test_auth_api.py
git commit -m "feat: POST /auth/register with token pair response"
```

---

### Task 7: POST /auth/login

**Files:**
- Modify: `backend/app/auth_routes.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_auth_api.py`)

```python
class TestLogin:
    def test_login_returns_token_pair(self, client):
        register(client)
        resp = client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": REGISTER["password"]},
        )
        assert resp.status_code == 200
        assert set(resp.json()) == {"access_token", "refresh_token", "token_type"}
        assert resp.headers["Cache-Control"] == "no-store"

    def test_wrong_password_and_unknown_email_are_identical_401s(self, client):
        register(client)
        wrong_pw = client.post(
            "/auth/login",
            json={"email": "alice@example.com", "password": "wrong-password"},
        )
        unknown = client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "whatever123"},
        )
        assert wrong_pw.status_code == unknown.status_code == 401
        assert wrong_pw.json() == unknown.json()
        assert wrong_pw.headers["WWW-Authenticate"] == "Bearer"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth_api.py -v`
Expected: new tests FAIL — 404 (no `/auth/login`)

- [ ] **Step 3: Implement** (append to `app/auth_routes.py`; add `LoginIn` to the schemas import)

```python
@router.post("/login", response_model=TokenPairOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.execute(
        select(models.User).where(models.User.email == payload.email)
    ).scalar_one_or_none()
    if user is None or user.password_hash is None:
        raise _credentials_error()
    if not security.verify_password(payload.password, user.password_hash):
        raise _credentials_error()
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(payload.password)
        db.commit()
    return _issue_token_pair(db, user, response)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_api.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/auth_routes.py tests/test_auth_api.py
git commit -m "feat: POST /auth/login with enumeration-safe 401"
```

---

### Task 8: get_current_user guard + GET /auth/me

**Files:**
- Modify: `backend/app/auth_routes.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_auth_api.py`)

```python
def auth_headers(client, **overrides):
    body = register(client, **overrides).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


class TestMe:
    def test_me_returns_current_user(self, client):
        headers = auth_headers(client)
        resp = client.get("/auth/me", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["username"] == "alice"
        assert body["email"] == "alice@example.com"
        assert "password_hash" not in body

    def test_missing_header_401(self, client):
        resp = client.get("/auth/me")
        assert resp.status_code == 401
        assert resp.headers["WWW-Authenticate"] == "Bearer"

    def test_garbage_token_401(self, client):
        resp = client.get(
            "/auth/me", headers={"Authorization": "Bearer not.a.jwt"}
        )
        assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth_api.py -v`
Expected: new tests FAIL — 404 (no `/auth/me`)

- [ ] **Step 3: Implement** (append to `app/auth_routes.py`; add `import jwt`, `Header` to the fastapi import, and `UserOut` to the schemas import)

```python
def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    if authorization is None or not authorization.startswith("Bearer "):
        raise _credentials_error()
    try:
        user_id = security.decode_access_token(authorization.removeprefix("Bearer "))
    except jwt.InvalidTokenError:
        raise _credentials_error()
    user = db.get(models.User, user_id)
    if user is None:
        raise _credentials_error()
    return user


@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_api.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/auth_routes.py tests/test_auth_api.py
git commit -m "feat: get_current_user guard and GET /auth/me"
```

---

### Task 9: POST /auth/refresh — atomic rotation + reuse detection

**Files:**
- Modify: `backend/app/auth_routes.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_auth_api.py`)

```python
from datetime import timedelta

from app import security
from app.delivery import utcnow
from app.models import RefreshToken, User


class TestRefresh:
    def test_rotation_returns_new_pair_and_revokes_old(self, client):
        old = register(client).json()
        resp = client.post(
            "/auth/refresh", json={"refresh_token": old["refresh_token"]}
        )
        assert resp.status_code == 200
        new = resp.json()
        assert new["refresh_token"] != old["refresh_token"]
        assert resp.headers["Cache-Control"] == "no-store"
        # The old token was revoked by rotation; replaying it must fail.
        replay = client.post(
            "/auth/refresh", json={"refresh_token": old["refresh_token"]}
        )
        assert replay.status_code == 401

    def test_reuse_detection_revokes_everything(self, client):
        old = register(client).json()
        new = client.post(
            "/auth/refresh", json={"refresh_token": old["refresh_token"]}
        ).json()
        # Replay the rotated token: reuse detection should kill the new one too.
        client.post("/auth/refresh", json={"refresh_token": old["refresh_token"]})
        resp = client.post(
            "/auth/refresh", json={"refresh_token": new["refresh_token"]}
        )
        assert resp.status_code == 401

    def test_unknown_token_401(self, client):
        resp = client.post("/auth/refresh", json={"refresh_token": "made-up"})
        assert resp.status_code == 401

    def test_expired_token_401(self, client, db_session):
        register(client)
        user = db_session.query(User).one()
        raw, token_hash = security.new_refresh_token()
        db_session.add(
            RefreshToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=utcnow() - timedelta(seconds=1),
                created_at=utcnow() - timedelta(days=31),
            )
        )
        db_session.commit()
        resp = client.post("/auth/refresh", json={"refresh_token": raw})
        assert resp.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth_api.py -v`
Expected: new tests FAIL — 404 (no `/auth/refresh`)

- [ ] **Step 3: Implement** (append to `app/auth_routes.py`; add `update` to the sqlalchemy import and `RefreshIn` to the schemas import)

```python
@router.post("/refresh", response_model=TokenPairOut)
def refresh(payload: RefreshIn, response: Response, db: Session = Depends(get_db)):
    now = utcnow()
    token = db.execute(
        select(models.RefreshToken).where(
            models.RefreshToken.token_hash
            == security.hash_refresh_token(payload.refresh_token)
        )
    ).scalar_one_or_none()
    if token is None:
        raise _credentials_error()
    if token.revoked_at is not None:
        # Replay of a rotated/revoked token — assume theft, revoke the lot.
        db.execute(
            update(models.RefreshToken)
            .where(
                models.RefreshToken.user_id == token.user_id,
                models.RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        db.commit()
        logger.warning("refresh token reuse detected for user %s", token.user_id)
        raise _credentials_error()
    # Atomic rotation: revoke-if-still-live-and-unexpired, then check rowcount.
    result = db.execute(
        update(models.RefreshToken)
        .where(
            models.RefreshToken.id == token.id,
            models.RefreshToken.revoked_at.is_(None),
            models.RefreshToken.expires_at > now,
        )
        .values(revoked_at=now)
    )
    db.commit()
    if (result.rowcount or 0) != 1:
        raise _credentials_error()  # expired, or lost a race
    user = db.get(models.User, token.user_id)
    if user is None:
        raise _credentials_error()
    return _issue_token_pair(db, user, response)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_api.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/auth_routes.py tests/test_auth_api.py
git commit -m "feat: POST /auth/refresh with atomic rotation and reuse detection"
```

---

### Task 10: POST /auth/logout

**Files:**
- Modify: `backend/app/auth_routes.py`
- Modify: `backend/tests/test_auth_api.py`

- [ ] **Step 1: Write the failing tests** (append to `tests/test_auth_api.py`)

```python
class TestLogout:
    def test_logout_revokes_refresh_token(self, client):
        pair = register(client).json()
        resp = client.post(
            "/auth/logout", json={"refresh_token": pair["refresh_token"]}
        )
        assert resp.status_code == 204
        resp = client.post(
            "/auth/refresh", json={"refresh_token": pair["refresh_token"]}
        )
        assert resp.status_code == 401

    def test_logout_is_idempotent(self, client):
        pair = register(client).json()
        client.post("/auth/logout", json={"refresh_token": pair["refresh_token"]})
        resp = client.post(
            "/auth/logout", json={"refresh_token": pair["refresh_token"]}
        )
        assert resp.status_code == 204
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_auth_api.py -v`
Expected: new tests FAIL — 404 (no `/auth/logout`)

- [ ] **Step 3: Implement** (append to `app/auth_routes.py`)

```python
@router.post("/logout", status_code=204)
def logout(payload: RefreshIn, db: Session = Depends(get_db)) -> None:
    # Always 204 — logout is idempotent and never confirms whether a token existed.
    db.execute(
        update(models.RefreshToken)
        .where(
            models.RefreshToken.token_hash
            == security.hash_refresh_token(payload.refresh_token),
            models.RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=utcnow())
    )
    db.commit()
```

Note: logout deliberately returns 204 for unknown tokens too (the spec's 401-for-revoked rule applies to `/auth/refresh`, where the caller needs to know to re-login; logout has nothing useful to leak).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_auth_api.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add app/auth_routes.py tests/test_auth_api.py
git commit -m "feat: idempotent POST /auth/logout"
```

---

### Task 11: Docs + final verification

**Files:**
- Modify: `README.md` (API at a glance section)
- Modify: `CLAUDE.md` (project status line + gotchas)

- [ ] **Step 1: Add auth endpoints to README's "API at a glance"** (insert before the messages list)

```markdown
- `POST /auth/register` — `{username, email, password}` → access + refresh token pair
- `POST /auth/login` — `{email, password}` → token pair
- `POST /auth/refresh` — `{refresh_token}` → rotated token pair (old one is revoked)
- `POST /auth/logout` — `{refresh_token}` revoked
- `GET /auth/me` — current user (send `Authorization: Bearer <access_token>`)

Set `JWT_SECRET` in real deployments; a dev default is baked in. Access tokens
last 15 minutes — use `/auth/refresh` to stay logged in.
```

- [ ] **Step 2: Update CLAUDE.md** — change the Phase 1 status sentence to mention password auth existing (Google OAuth and message-user linkage still to come), and add a gotcha:

```markdown
- Refresh tokens rotate on every use; replaying an old one revokes all of a user's tokens (reuse detection). Tests that refresh twice must use the newest token.
```

- [ ] **Step 3: Run the full suite one last time**

Run: `pytest`
Expected: all PASS (existing message/delivery/scheduler tests untouched and green)

- [ ] **Step 4: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: auth endpoints in README, auth status + gotcha in CLAUDE.md"
```

---

## Out of scope for this milestone

- Messages remain string-addressed (milestone 2: FKs, ownership rules, `PRAGMA foreign_keys=ON`, index swap, drop/recreate dev DB).
- Google OAuth, SessionMiddleware, authlib/itsdangerous deps (milestone 3).
- HttpOnly-cookie token delivery (frontend milestone).
