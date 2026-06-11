"""Auth primitives: password hashing, access JWTs, refresh tokens. No DB access."""
import hashlib
import os
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.delivery import utcnow

JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-not-for-production-pad-to-32-bytes")
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
    except (VerificationError, InvalidHashError):
        # VerifyMismatchError subclasses VerificationError; malformed stored
        # hashes must look like bad credentials, not crash the endpoint.
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """Call only after verify_password succeeds — raises on malformed hashes."""
    return _hasher.check_needs_rehash(password_hash)


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
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        raise jwt.InvalidTokenError("invalid subject") from None


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    """Returns (raw token for the client, sha256 hex hash for the DB)."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)
