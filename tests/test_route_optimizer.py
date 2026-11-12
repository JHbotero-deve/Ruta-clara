import math
from dataclasses import dataclass
from src.route_optimizer import haversine, calculate_optimal_route


@dataclass
class SimpleLocation:
    name: str
    latitude: float
    longitude: float


def test_haversine_same_point():
    """Distance between identical points must be 0."""
    dist = haversine(6.2442, -75.5812, 6.2442, -75.5812)
    assert math.isclose(dist, 0.0, abs_tol=1e-5)


def test_haversine_known_distance():
    """Medellín to Envigado distance (~10 km approx)."""
    # Medellín (Parque Berrío) -> Envigado (Parque Envigado)
    dist = haversine(6.2492, -75.5684, 6.1706, -75.5852)
    assert 8.0 <= dist <= 12.0


def test_calculate_optimal_route_empty_or_single():
    assert calculate_optimal_route([]) == []

    single = [SimpleLocation("A", 6.2, -75.5)]
    assert calculate_optimal_route(single) == single


def test_calculate_optimal_route_small_set():
    """Test N <= 8 brute force optimizer."""
    locations = [
        SimpleLocation("Point A", 6.20, -75.50),
        SimpleLocation("Point B", 6.25, -75.55),
        SimpleLocation("Point C", 6.22, -75.52),
        SimpleLocation("Point D", 6.18, -75.48),
    ]
    route = calculate_optimal_route(locations)
    assert len(route) == 4
    # All original locations must be present
    names = {loc.name for loc in route}
    assert names == {"Point A", "Point B", "Point C", "Point D"}


def test_calculate_optimal_route_large_set_2opt():
    """Test N > 8 Nearest Neighbor + 2-Opt optimizer."""
    locations = [
        SimpleLocation(f"Loc_{i}", 6.20 + (i * 0.01), -75.50 - (i * 0.01))
        for i in range(12)
    ]
    route = calculate_optimal_route(locations)
    assert len(route) == 12
    assert len(set(loc.name for loc in route)) == 12
