import logging
import math
import os
import random
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import DELIVERED, IN_FLIGHT, LOST, Message

logger = logging.getLogger(__name__)

PIGEON_SPEED_KMH = 80.0
BASE_LOSS_PROBABILITY = 0.02
LOSS_PER_1000_KM = 0.01
MAX_LOSS_PROBABILITY = 0.15


def utcnow() -> datetime:
    """Naive UTC now — the one datetime convention for the whole app."""
    return datetime.now(UTC).replace(tzinfo=None)


def fast_forward_factor() -> float:
    """Time-scale factor from the FAST_FORWARD env var. Unset means 1 (real time)."""
    raw = os.environ.get("FAST_FORWARD")
    if raw is None:
        return 1.0
    try:
        factor = float(raw)
    except ValueError:
        raise ValueError(f"FAST_FORWARD must be a number, got {raw!r}") from None
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError(f"FAST_FORWARD must be a finite number > 0, got {factor}")
    return factor


def flight_duration(distance_km: float) -> timedelta:
    """Real-time duration of a pigeon flight, FAST_FORWARD applied."""
    pigeon_hours = distance_km / PIGEON_SPEED_KMH
    return timedelta(hours=pigeon_hours / fast_forward_factor())


def loss_probability(distance_km: float) -> float:
    """Chance the pigeon never arrives: 2% base + 1% per 1000 km, capped at 15%."""
    return min(
        BASE_LOSS_PROBABILITY + LOSS_PER_1000_KM * (distance_km / 1000.0),
        MAX_LOSS_PROBABILITY,
    )


def resolve_due_messages(
    session: Session,
    rng: Callable[[], float] = random.random,
    now: datetime | None = None,
) -> int:
    """Roll fate for overdue in-flight messages. Returns how many were resolved.

    Idempotent under overlapping sweeps: the UPDATE only applies while the row
    is still in_flight, and each row commits independently so SQLite write
    locks stay brief.
    """
    if now is None:
        now = utcnow()
    due = session.execute(
        select(Message.id, Message.distance_km).where(
            Message.status == IN_FLIGHT, Message.arrival_at <= now
        )
    ).all()
    resolved = 0
    for message_id, distance_km in due:
        try:
            status = LOST if rng() < loss_probability(distance_km) else DELIVERED
            result = session.execute(
                update(Message)
                .where(Message.id == message_id, Message.status == IN_FLIGHT)
                .values(status=status, resolved_at=now)
            )
            session.commit()
            resolved += result.rowcount or 0
        except Exception:
            # One bad row must not poison the rest of the batch.
            session.rollback()
            logger.exception("failed to resolve message %s", message_id)
    return resolved
