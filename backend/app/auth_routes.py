import logging

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import models, security
from app.db import get_db
from app.delivery import utcnow
from app.schemas import LoginIn, RefreshIn, RegisterIn, TokenPairOut, UserOut

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
