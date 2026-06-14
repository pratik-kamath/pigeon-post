from datetime import datetime

from app.auth_routes import _generate_username
from app.models import User


def _seed(db_session, username):
    db_session.add(User(
        username=username, email=f"{username}@example.com",
        password_hash="x", created_at=datetime(2026, 6, 14),
    ))
    db_session.commit()


def test_generates_from_email_local_part(db_session):
    assert _generate_username(db_session, "alex@example.com", "Alex") == "alex"


def test_sanitizes_disallowed_chars(db_session):
    assert _generate_username(db_session, "a.l-e+x@example.com", None) == "alex"


def test_collision_appends_suffix(db_session):
    _seed(db_session, "alex")
    assert _generate_username(db_session, "alex@example.com", None) == "alex1"


def test_second_collision_increments(db_session):
    _seed(db_session, "alex")
    _seed(db_session, "alex1")
    assert _generate_username(db_session, "alex@example.com", None) == "alex2"


def test_short_seed_is_padded(db_session):
    result = _generate_username(db_session, "ab@example.com", None)
    assert len(result) >= 3 and result.startswith("ab")


def test_falls_back_to_name_when_seed_too_short(db_session):
    assert _generate_username(db_session, "a@example.com", "Bob") == "bob"


def test_empty_seed_falls_back_to_pigeon(db_session):
    # non-ASCII local part sanitizes to empty, no usable name
    assert _generate_username(db_session, "区@example.com", None) == "pigeon"


def test_collision_is_case_insensitive(db_session):
    _seed(db_session, "Alex")  # stored mixed-case; collides case-insensitively
    assert _generate_username(db_session, "alex@example.com", None) == "alex1"


def test_suffix_keeps_length_within_30(db_session):
    _seed(db_session, "a" * 30)
    result = _generate_username(db_session, "a" * 40 + "@example.com", None)
    assert len(result) <= 30
    assert result != "a" * 30
