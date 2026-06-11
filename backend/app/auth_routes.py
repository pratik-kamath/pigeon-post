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
        db.commit()
    except IntegrityError:
        # Unique-index backstop for races the pre-check missed.
        db.rollback()
        raise HTTPException(status_code=409, detail="username or email already taken")
    db.refresh(user)
    return _issue_token_pair(db, user, response)
