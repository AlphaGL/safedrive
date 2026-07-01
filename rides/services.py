"""Domain services shared by HTTP views and WebSocket consumers."""
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import EmergencyAlert, Ride
from .notifications import dispatch_alert


def _broadcast_alert_to_ride(ride, alert):
    layer = get_channel_layer()
    if layer is None or ride is None:
        return
    async_to_sync(layer.group_send)(
        f"ride_{ride.id}",
        {
            "type": "alert.message",
            "alert": {
                "kind": alert.get_kind_display(),
                "message": alert.message,
                "status": alert.status,
            },
        },
    )


def create_sos(ride, rider, lat=None, lng=None, location="", raised_by=None):
    """Persist an SOS alert and fan out to contacts + admin + ride viewers."""
    alert = EmergencyAlert.objects.create(
        ride=ride,
        rider=rider,
        raised_by=raised_by or rider,
        kind=EmergencyAlert.Kind.SOS,
        latitude=lat,
        longitude=lng,
        location=location,
        message="SOS triggered by rider during active trip.",
    )
    notified = dispatch_alert(alert)
    _broadcast_alert_to_ride(ride, alert)
    return alert, notified


def raise_safety_alert(ride, kind, message, lat=None, lng=None):
    """Create a safety alert from automated detection (dedupe active ones)."""
    existing = EmergencyAlert.objects.filter(
        ride=ride, kind=kind, status=EmergencyAlert.Status.ACTIVE
    ).first()
    if existing:
        return existing
    alert = EmergencyAlert.objects.create(
        ride=ride,
        rider=ride.rider,
        raised_by=None,
        kind=kind,
        latitude=lat,
        longitude=lng,
        message=message,
    )
    dispatch_alert(alert)
    return alert


def broadcast_ride_status(ride):
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        f"ride_{ride.id}",
        {"type": "status.message", "status": ride.status},
    )


def driver_group(driver_id):
    return f"driver_{driver_id}"


def notify_driver_of_request(ride):
    """Push a live ride request to the targeted driver's dashboard."""
    if ride.driver_id is None:
        return
    layer = get_channel_layer()
    if layer is None:
        return
    async_to_sync(layer.group_send)(
        driver_group(ride.driver_id),
        {
            "type": "request.message",
            "request": {
                "ride_id": ride.id,
                "rider": ride.rider.name,
                "pickup": ride.pickup_location,
                "destination": ride.destination,
                "eta": ride.eta_minutes,
            },
        },
    )
