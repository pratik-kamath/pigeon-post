from datetime import timedelta

import jwt
import pytest

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

    def test_malformed_stored_hash_is_invalid_not_error(self):
        # A corrupt DB value must read as "wrong password", never a 500.
        assert not security.verify_password("pw", "not-an-argon2-hash")


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
            "not-the-real-secret-pad-to-32-bytes-here",
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

    def test_non_integer_sub_rejected(self):
        # Validly signed but garbage sub must be InvalidTokenError, not ValueError.
        bad = jwt.encode(
            {"sub": "abc", "iat": 0, "exp": 9999999999, "iss": security.JWT_ISSUER},
            security.JWT_SECRET,
            algorithm="HS256",
        )
        with pytest.raises(jwt.InvalidTokenError):
            security.decode_access_token(bad)

    def test_alg_none_rejected(self):
        # The fixed algorithms list must reject unsigned alg=none tokens.
        unsigned = jwt.encode(
            {"sub": "42", "iat": 0, "exp": 9999999999, "iss": security.JWT_ISSUER},
            None,
            algorithm="none",
        )
        with pytest.raises(jwt.InvalidTokenError):
            security.decode_access_token(unsigned)
