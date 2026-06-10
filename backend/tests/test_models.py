from datetime import timedelta

from app.delivery import utcnow
from app.models import IN_FLIGHT, Message


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
