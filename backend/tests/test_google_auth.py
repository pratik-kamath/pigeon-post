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
        assert audience == CLIENT_ID  # the seam must pass our client id as the aud
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


@pytest.mark.parametrize("override", [{"sub": None}, {"email": None}, {"email": "   "}])
def test_missing_sub_or_email_rejected(monkeypatch, override):
    _patch_verify(monkeypatch, result=_claims(**override))
    with pytest.raises(InvalidGoogleToken):
        verify_google_id_token("tok")


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None, "True", False])
def test_email_verified_is_strict(monkeypatch, value):
    _patch_verify(monkeypatch, result=_claims(email_verified=value))
    assert verify_google_id_token("tok").email_verified is False
