import pytest

from app.cities import CITIES, distance_between


def test_catalog_has_cities_with_coordinates():
    assert len(CITIES) >= 15
    for name, (lat, lon) in CITIES.items():
        assert name == name.strip().lower()
        assert -90 <= lat <= 90
        assert -180 <= lon <= 180


def test_london_paris_distance_within_one_percent():
    # Known great-circle distance ~343.8 km
    assert distance_between("london", "paris") == pytest.approx(343.8, rel=0.01)


def test_distance_is_symmetric():
    assert distance_between("new york", "san francisco") == pytest.approx(
        distance_between("san francisco", "new york")
    )


def test_nyc_sf_is_about_4130_km():
    assert distance_between("new york", "san francisco") == pytest.approx(4130, rel=0.01)
