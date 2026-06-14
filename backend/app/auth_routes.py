import logging
import re

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, security
from app.db import get_db
from app.delivery import utcnow
from app.google_auth import (
    GoogleVerifyUnavailable,
    InvalidGoogleToken,
    verify_google_id_token,
)
from app.schemas import (
    GoogleLoginIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPairOut,
    UserOut,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


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
            # Both sides lowered — matches the functional unique indexes and
            # stays correct even if a future write path forgets to normalize.
            (func.lower(models.User.username) == payload.username.lower())
            | (func.lower(models.User.email) == payload.email.lower())
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
        # flush assigns user.id and trips the unique-index backstop for races
        # the pre-check missed — without committing, so the user row and the
        # refresh token land in one transaction (committed in _issue_token_pair).
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="username or email already taken"
        ) from exc
    return _issue_token_pair(db, user, response)


@router.post("/login", response_model=TokenPairOut)
def login(payload: LoginIn, response: Response, db: Session = Depends(get_db)):
    user = db.execute(
        select(models.User).where(
            func.lower(models.User.email) == payload.email.lower()
        )
    ).scalar_one_or_none()
    if user is None or user.password_hash is None:
        raise _credentials_error()
    if not security.verify_password(payload.password, user.password_hash):
        raise _credentials_error()
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(payload.password)
        db.commit()
    return _issue_token_pair(db, user, response)


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


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    # RFC 7235: scheme is case-insensitive; parse it explicitly.
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _credentials_error()
    try:
        user_id = security.decode_access_token(token.strip())
    except jwt.InvalidTokenError:
        raise _credentials_error()
    user = db.get(models.User, user_id)
    if user is None:
        raise _credentials_error()
    return user


@router.get("/me", response_model=UserOut)
def me(current_user: models.User = Depends(get_current_user)):
    return current_user


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
        # Either expired, or a concurrent refresh revoked it between our
        # SELECT and UPDATE. The latter is still a second presentation of the
        # same token — same theft assumption as the replay branch above.
        db.refresh(token)
        if token.revoked_at is not None:
            db.execute(
                update(models.RefreshToken)
                .where(
                    models.RefreshToken.user_id == token.user_id,
                    models.RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            db.commit()
            logger.warning(
                "refresh token reuse detected for user %s", token.user_id
            )
        raise _credentials_error()
    user = db.get(models.User, token.user_id)
    if user is None:
        raise _credentials_error()
    return _issue_token_pair(db, user, response)


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
