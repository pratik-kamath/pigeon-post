"""Auth primitives: password hashing, access JWTs, refresh tokens. No DB access."""
import hashlib
import os
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

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
    except (VerificationError, InvalidHashError):
        # VerifyMismatchError subclasses VerificationError; malformed stored
        # hashes must look like bad credentials, not crash the endpoint.
        return False


def password_needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)
