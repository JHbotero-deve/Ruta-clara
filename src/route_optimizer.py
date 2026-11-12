"""Route optimization module for Ruta Clara.

Implements TSP (Travelling Salesman Problem) solving via:
- Exact brute-force for N <= 8 locations (O(N!) — guaranteed optimal)
- Nearest Neighbor heuristic for N > 8 locations (O(N²) — fast approximation)

Distance calculation uses the Haversine formula for great-circle distances.
"""

import math
from itertools import permutations
from typing import List, Any

EARTH_RADIUS_KM = 6371.0


def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on Earth.

    Uses the Haversine formula to compute the shortest distance over
    the earth's surface between two points specified by latitude and
    longitude in decimal degrees.

    Args:
        lat1: Latitude of point 1 in decimal degrees.
        lon1: Longitude of point 1 in decimal degrees.
        lat2: Latitude of point 2 in decimal degrees.
        lon2: Longitude of point 2 in decimal degrees.

    Returns:
        Distance in kilometers.
    """
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c


def _two_opt(route_indices: List[int], distances: dict) -> List[int]:
    """Apply 2-opt local search optimization to uncross intersecting route paths."""
    n = len(route_indices)
    if n <= 3:
        return route_indices

    best_route = list(route_indices)
    improved = True
    max_iterations = 100
    iteration = 0

    while improved and iteration < max_iterations:
        improved = False
        iteration += 1
        for i in range(1, n - 2):
            for j in range(i + 1, n - 1):
                # Calculate current edge costs vs reversed edge costs
                d_current = (
                    distances[(best_route[i - 1], best_route[i])]
                    + distances[(best_route[j], best_route[j + 1])]
                )
                d_proposed = (
                    distances[(best_route[i - 1], best_route[j])]
                    + distances[(best_route[i], best_route[j + 1])]
                )
                if d_proposed < d_current - 1e-6:
                    best_route[i : j + 1] = reversed(best_route[i : j + 1])
                    improved = True

    return best_route


def calculate_optimal_route(locations: List[Any]) -> List[Any]:
    """Return locations reordered to form an optimal delivery route.

    Solves the Travelling Salesman Problem (TSP):
    - For N <= 8: exact solution evaluating all permutations (O(N!)).
    - For N > 8: Nearest Neighbor + 2-Opt local search refinement (O(N²)).

    Args:
        locations: List of location objects with `.latitude` and `.longitude`.

    Returns:
        The same locations list reordered for minimal total travel distance.
    """
    if not locations or len(locations) <= 1:
        return list(locations) if locations else []

    n = len(locations)

    # Precalculate full distance matrix
    distances = {}
    for i, loc1 in enumerate(locations):
        distances[(i, i)] = 0.0
        for j, loc2 in enumerate(locations):
            if i != j:
                distances[(i, j)] = haversine(
                    loc1.latitude, loc1.longitude,
                    loc2.latitude, loc2.longitude,
                )

    # For small N, brute-force exact optimal path
    if n <= 8:
        min_distance = float("inf")
        optimal_perm = tuple(range(n))
        for perm in permutations(range(n)):
            total_distance = sum(
                distances[(perm[i], perm[i + 1])]
                for i in range(len(perm) - 1)
            )
            if total_distance < min_distance:
                min_distance = total_distance
                optimal_perm = perm
        return [locations[i] for i in optimal_perm]

    # For larger N, use Nearest Neighbor algorithm + 2-Opt local search
    unvisited = set(range(1, n))
    current = 0
    route_indices = [current]

    while unvisited:
        next_loc = min(unvisited, key=lambda idx: distances[(current, idx)])
        unvisited.remove(next_loc)
        route_indices.append(next_loc)
        current = next_loc

    # Optimize route with 2-Opt
    optimized_indices = _two_opt(route_indices, distances)

    return [locations[i] for i in optimized_indices]
