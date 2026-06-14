def test_cities_returns_full_catalog(client):
    resp = client.get("/cities")
    assert resp.status_code == 200
    cities = resp.json()
    assert len(cities) == 20
    names = [c["name"] for c in cities]
    assert names == sorted(names)              # sorted by name
    assert all(n == n.lower() for n in names)  # lowercase catalog keys
    tokyo = next(c for c in cities if c["name"] == "tokyo")
    assert tokyo["lat"] == 35.6762 and tokyo["lon"] == 139.6503
    assert set(cities[0]) == {"name", "lat", "lon"}


def test_cities_is_public(client):
    assert client.get("/cities").status_code == 200
