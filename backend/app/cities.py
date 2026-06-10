import math

EARTH_RADIUS_KM = 6371.0

CITIES: dict[str, tuple[float, float]] = {
    "amsterdam": (52.3676, 4.9041),
    "berlin": (52.5200, 13.4050),
    "cairo": (30.0444, 31.2357),
    "cape town": (-33.9249, 18.4241),
    "chicago": (41.8781, -87.6298),
    "dubai": (25.2048, 55.2708),
    "hong kong": (22.3193, 114.1694),
    "istanbul": (41.0082, 28.9784),
    "london": (51.5074, -0.1278),
    "los angeles": (34.0522, -118.2437),
    "melbourne": (-37.8136, 144.9631),
    "mexico city": (19.4326, -99.1332),
    "mumbai": (19.0760, 72.8777),
    "new york": (40.7128, -74.0060),
    "paris": (48.8566, 2.3522),
    "rio de janeiro": (-22.9068, -43.1729),
    "san francisco": (37.7749, -122.4194),
    "singapore": (1.3521, 103.8198),
    "sydney": (-33.8688, 151.2093),
    "tokyo": (35.6762, 139.6503),
}


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))


def distance_between(origin: str, destination: str) -> float:
    """Great-circle distance in km between two catalog cities."""
    return haversine_km(CITIES[origin], CITIES[destination])
