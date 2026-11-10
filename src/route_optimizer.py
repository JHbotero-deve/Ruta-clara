import math
from itertools import permutations

EARTH_RADIUS_KM = 6371.0

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points in kilometers."""
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_KM * c

def calculate_optimal_route(locations):
    """
    Returns an ordered list of locations representing an optimal route.
    Uses exact TSP solution (permutations) for small sets (<=8)
    and Nearest Neighbor heuristic for larger sets to maintain high performance.
    """
    if not locations or len(locations) <= 1:
        return locations

    n = len(locations)

    # Precalculate distance matrix
    distances = {}
    for i, loc1 in enumerate(locations):
        for j, loc2 in enumerate(locations):
            if i != j:
                distances[(i, j)] = haversine(loc1.latitude, loc1.longitude, loc2.latitude, loc2.longitude)

    # For small N, brute-force exact optimal path
    if n <= 8:
        min_distance = float("inf")
        optimal_perm = None
        for perm in permutations(range(n)):
            total_distance = sum(distances[(perm[i], perm[i + 1])] for i in range(len(perm) - 1))
            if total_distance < min_distance:
                min_distance = total_distance
                optimal_perm = perm
        return [locations[i] for i in optimal_perm]

    # For larger N, use Nearest Neighbor algorithm for scalability
    unvisited = set(range(1, n))
    current = 0
    route_indices = [current]

    while unvisited:
        next_loc = min(unvisited, key=lambda idx: distances[(current, idx)])
        unvisited.remove(next_loc)
        route_indices.append(next_loc)
        current = next_loc

    return [locations[i] for i in route_indices]
