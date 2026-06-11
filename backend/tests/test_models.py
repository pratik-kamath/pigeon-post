import pytest
from datetime import datetime, timedelta

from sqlalchemy.exc import IntegrityError

from app.delivery import utcnow
from app.models import IN_FLIGHT, Message, RefreshToken, User


def test_message_roundtrip(db_session):
    sent = utcnow()
    message = Message(
        sender="pratik",
        recipient="alex",
        body="wish you were here",
        origin="new york",
        destination="san francisco",
        distance_km=4130.0,
        status=IN_FLIGHT,
        sent_at=sent,
        arrival_at=sent + timedelta(hours=51),
    )
    db_session.add(message)
    db_session.commit()

    loaded = db_session.get(Message, message.id)
    assert loaded.status == IN_FLIGHT
    assert loaded.resolved_at is None
    assert loaded.arrival_at - loaded.sent_at == timedelta(hours=51)


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
