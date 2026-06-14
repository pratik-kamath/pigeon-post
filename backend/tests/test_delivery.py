from datetime import datetime, timedelta

import pytest

from app.delivery import (
    BASE_LOSS_PROBABILITY,
    MAX_LOSS_PROBABILITY,
    fast_forward_factor,
    flight_duration,
    loss_probability,
    resolve_due_messages,
)
from app.models import DELIVERED, IN_FLIGHT, LOST, Message, User


def test_flight_duration_at_pigeon_speed(monkeypatch):
    monkeypatch.delenv("FAST_FORWARD", raising=False)
    # 80 km at 80 km/h = 1 hour
    assert flight_duration(80.0) == timedelta(hours=1)


def test_fast_forward_scales_duration(monkeypatch):
    monkeypatch.setenv("FAST_FORWARD", "120")
    # 80 km -> 1 pigeon-hour -> 30 real seconds at 120x
    assert flight_duration(80.0) == timedelta(seconds=30)


def test_fast_forward_unset_means_real_time(monkeypatch):
    monkeypatch.delenv("FAST_FORWARD", raising=False)
    assert fast_forward_factor() == 1.0


@pytest.mark.parametrize("bad", ["banana", "0", "-5", "nan", "inf"])
def test_invalid_fast_forward_fails_clearly(monkeypatch, bad):
    monkeypatch.setenv("FAST_FORWARD", bad)
    with pytest.raises(ValueError, match="FAST_FORWARD"):
        fast_forward_factor()


def test_loss_probability_base():
    assert loss_probability(0.0) == pytest.approx(BASE_LOSS_PROBABILITY)


def test_loss_probability_scales_with_distance():
    # 2% base + 1% per 1000 km
    assert loss_probability(5000.0) == pytest.approx(0.07)


def test_loss_probability_is_capped():
    assert loss_probability(50_000.0) == pytest.approx(MAX_LOSS_PROBABILITY)


NOW = datetime(2026, 6, 11, 12, 0, 0)


def _ensure_users(db_session):
    sender = db_session.query(User).filter_by(username="sender").one_or_none()
    if sender is None:
        sender = User(username="sender", email="sender@example.com",
                      password_hash="x", created_at=NOW)
        recipient = User(username="recipient", email="recipient@example.com",
                         password_hash="x", created_at=NOW)
        db_session.add_all([sender, recipient])
        db_session.commit()
        return sender.id, recipient.id
    recipient = db_session.query(User).filter_by(username="recipient").one()
    return sender.id, recipient.id


def make_message(db_session, *, arrival_at, status=IN_FLIGHT, distance_km=4130.0):
    sender_id, recipient_id = _ensure_users(db_session)
    message = Message(
        sender_id=sender_id,
        recipient_id=recipient_id,
        body="hello",
        origin="new york",
        destination="san francisco",
        distance_km=distance_km,
        status=status,
        sent_at=datetime(2026, 6, 9, 12, 0, 0),
        arrival_at=arrival_at,
    )
    db_session.add(message)
    db_session.commit()
    return message


def test_overdue_message_is_delivered_when_roll_survives(db_session):
    message = make_message(db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0))
    count = resolve_due_messages(db_session, rng=lambda: 0.999, now=NOW)
    assert count == 1
    db_session.refresh(message)
    assert message.status == DELIVERED
    assert message.resolved_at == NOW


def test_overdue_message_is_lost_when_roll_fails(db_session):
    message = make_message(db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0))
    resolve_due_messages(db_session, rng=lambda: 0.0, now=NOW)
    db_session.refresh(message)
    assert message.status == LOST


def test_roll_exactly_at_probability_boundary_is_delivered(db_session):
    message = make_message(db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0))
    boundary = loss_probability(message.distance_km)
    resolve_due_messages(db_session, rng=lambda: boundary, now=NOW)
    db_session.refresh(message)
    assert message.status == DELIVERED  # lost only when rng() < p


def test_future_message_left_alone(db_session):
    message = make_message(db_session, arrival_at=datetime(2026, 6, 12, 12, 0, 0))
    count = resolve_due_messages(db_session, rng=lambda: 0.0, now=NOW)
    assert count == 0
    db_session.refresh(message)
    assert message.status == IN_FLIGHT
    assert message.resolved_at is None


def test_already_resolved_message_untouched(db_session):
    message = make_message(
        db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0), status=DELIVERED
    )
    count = resolve_due_messages(db_session, rng=lambda: 0.0, now=NOW)
    assert count == 0
    db_session.refresh(message)
    assert message.status == DELIVERED


def test_sweep_resolves_multiple_due_messages(db_session):
    rolls = iter([0.0, 0.999])
    due_lost = make_message(db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0))
    due_delivered = make_message(db_session, arrival_at=datetime(2026, 6, 11, 10, 0, 0))
    future = make_message(db_session, arrival_at=datetime(2026, 6, 12, 12, 0, 0))
    already = make_message(
        db_session, arrival_at=datetime(2026, 6, 11, 9, 0, 0), status=DELIVERED
    )

    count = resolve_due_messages(db_session, rng=lambda: next(rolls), now=NOW)

    assert count == 2
    for message in (due_lost, due_delivered, future, already):
        db_session.refresh(message)
    assert due_lost.status == LOST
    assert due_delivered.status == DELIVERED
    assert future.status == IN_FLIGHT
    assert already.status == DELIVERED


def test_one_bad_row_does_not_poison_the_batch(db_session):
    def exploding_then_fine():
        if not hasattr(exploding_then_fine, "called"):
            exploding_then_fine.called = True
            raise RuntimeError("boom")
        return 0.999

    bad = make_message(db_session, arrival_at=datetime(2026, 6, 11, 11, 0, 0))
    good = make_message(db_session, arrival_at=datetime(2026, 6, 11, 10, 0, 0))

    count = resolve_due_messages(db_session, rng=exploding_then_fine, now=NOW)

    assert count == 1
    db_session.refresh(bad)
    db_session.refresh(good)
    assert bad.status == IN_FLIGHT
    assert good.status == DELIVERED
