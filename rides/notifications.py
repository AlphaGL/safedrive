"""Notification fan-out for emergencies.

In a real deployment these would call an SMS gateway (Twilio), email, and push
services. Here we log + broadcast over the channel layer so the admin dashboard
and any open trip-share pages update instantly. Swap the body of
`_send_to_contact` for a real provider.
"""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger("safedrive.notifications")

ADMIN_ALERTS_GROUP = "admin_alerts"


def _send_to_contact(contact, alert):
    logger.warning(
        "EMERGENCY notification -> %s (%s / %s): %s alert for rider %s at %s",
        contact.name,
        contact.phone,
        contact.email or "no-email",
        alert.get_kind_display(),
        alert.rider.name,
        alert.location or f"{alert.latitude},{alert.longitude}",
    )
    # TODO: integrate Twilio SMS / SendGrid email here.


def notify_trusted_contacts(alert):
    contacts = alert.rider.trusted_contacts.all()
    for contact in contacts:
        _send_to_contact(contact, alert)
    return contacts.count()


def broadcast_admin_alert(alert):
    """Push the alert to every admin connected to the alerts WebSocket group."""
    layer = get_channel_layer()
    if layer is None:
        return
    payload = {
        "type": "alert.message",
        "alert": {
            "id": alert.pk,
            "kind": alert.get_kind_display(),
            "rider": alert.rider.name,
            "ride_id": alert.ride_id,
            "location": alert.location,
            "lat": alert.latitude,
            "lng": alert.longitude,
            "status": alert.status,
            "created_at": alert.created_at.isoformat(),
            "message": alert.message,
        },
    }
    async_to_sync(layer.group_send)(ADMIN_ALERTS_GROUP, payload)


def dispatch_alert(alert):
    """Single entry point: persist already done by caller; fan out everywhere."""
    count = notify_trusted_contacts(alert)
    broadcast_admin_alert(alert)
    return count
