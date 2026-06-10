from datetime import timedelta

import pytest

from app.delivery import (
    BASE_LOSS_PROBABILITY,
    MAX_LOSS_PROBABILITY,
    fast_forward_factor,
    flight_duration,
    loss_probability,
)


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


@pytest.mark.parametrize("bad", ["banana", "0", "-5"])
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
