"""Google ID token verification. No DB access."""
import os
from dataclasses import dataclass

from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
_ACCEPTED_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})
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
        # GoogleAuthError: wrong issuer or other auth-level failure.
        raise InvalidGoogleToken(str(exc)) from exc
    # Defensive (older google-auth versions didn't check iss inside verify):
    if claims.get("iss") not in _ACCEPTED_ISSUERS:
        raise InvalidGoogleToken("untrusted issuer")
    sub, email = claims.get("sub"), claims.get("email")
    if not sub or not email or not email.strip():
        raise InvalidGoogleToken("missing sub/email")
    return GoogleIdentity(
        sub=sub,
        email=email.strip().lower(),  # match the lowercased unique index
        # Strict: only a real boolean True passes (avoids bool("false") == True).
        email_verified=claims.get("email_verified") is True,
        name=claims.get("name"),
    )
