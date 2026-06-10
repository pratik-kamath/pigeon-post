import math
import os
from datetime import UTC, datetime, timedelta

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
