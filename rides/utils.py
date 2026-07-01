"""Geo + safety helpers: distance math, ETA, route-deviation detection."""
import math

from django.conf import settings
from django.utils import timezone

EARTH_RADIUS_M = 6_371_000


def haversine_m(lat1, lng1, lat2, lng2):
    """Great-circle distance between two points in metres."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def distance_to_route_m(lat, lng, route):
    """Smallest distance from a point to any vertex of the planned route.

    A vertex-based approximation is plenty for flagging gross deviations and
    avoids heavy point-to-segment geometry.
    """
    if not route:
        return 0.0
    return min(haversine_m(lat, lng, pt[0], pt[1]) for pt in route)


def estimate_eta_minutes(distance_m, avg_speed_kmh=30):
    """Rough ETA assuming a city average speed."""
    if avg_speed_kmh <= 0:
        return None
    hours = (distance_m / 1000) / avg_speed_kmh
    return max(1, round(hours * 60))


def build_straight_route(start, end, points=12):
    """Interpolate a simple straight-line 'planned route' between two points.

    A real deployment would call a routing API (OSRM/Google Directions); this
    keeps the project self-contained and key-free.
    """
    (lat1, lng1), (lat2, lng2) = start, end
    return [
        [lat1 + (lat2 - lat1) * i / points, lng1 + (lng2 - lng1) * i / points]
        for i in range(points + 1)
    ]


def evaluate_safety(ride, lat, lng):
    """Inspect a new GPS ping against safety rules.

    Returns a list of (kind, message) tuples for any triggered warning.
    """
    warnings = []

    # 1. Route deviation
    deviation = distance_to_route_m(lat, lng, ride.planned_route)
    if deviation > settings.ROUTE_DEVIATION_METERS:
        warnings.append(
            (
                "route_deviation",
                f"Vehicle is {int(deviation)} m off the planned route.",
            )
        )

    # 2. Stationary too long
    recent = list(ride.tracking_points.order_by("-timestamp")[:20])
    if recent:
        oldest = recent[-1]
        moved = haversine_m(lat, lng, oldest.latitude, oldest.longitude)
        elapsed = (timezone.now() - oldest.timestamp).total_seconds()
        if (
            moved < settings.STATIONARY_METERS
            and elapsed > settings.STATIONARY_SECONDS
        ):
            warnings.append(
                (
                    "stationary",
                    f"Vehicle has barely moved for {int(elapsed // 60)} min.",
                )
            )

    # 3. ETA exceeded
    if ride.start_time and ride.eta_minutes:
        elapsed_min = (timezone.now() - ride.start_time).total_seconds() / 60
        if elapsed_min > ride.eta_minutes * 1.5:
            warnings.append(
                ("eta_exceeded", "Trip is taking far longer than estimated.")
            )

    return warnings
