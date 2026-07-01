"""Channels consumers for real-time tracking and emergency alerts."""
import json

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from .notifications import ADMIN_ALERTS_GROUP


def ride_group(ride_id):
    return f"ride_{ride_id}"


class RideTrackingConsumer(AsyncJsonWebsocketConsumer):
    """Bi-directional channel for one ride.

    - Drivers push `{action: 'location', lat, lng}` updates.
    - Riders, admins and trip-share viewers receive `location` and `alert`
      broadcasts. Anyone may connect read-only with the share token.
    """

    async def connect(self):
        self.ride_id = self.scope["url_route"]["kwargs"]["ride_id"]
        self.group = ride_group(self.ride_id)

        self.ride = await self._get_ride(self.ride_id)
        if self.ride is None:
            await self.close()
            return

        # Authorisation: participant, admin, or correct share token.
        token = self._query_param("token")
        self.can_write = await self._can_write(self.ride, self.scope["user"])
        allowed = self.can_write or await self._can_read(
            self.ride, self.scope["user"], token
        )
        if not allowed:
            await self.close()
            return

        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

        # Send the last known point + planned route on connect.
        last = await self._last_point(self.ride)
        await self.send_json(
            {
                "type": "init",
                "status": self.ride.status,
                "planned_route": self.ride.planned_route,
                "last": last,
                "can_write": self.can_write,
            }
        )

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content):
        action = content.get("action")
        if action == "location" and self.can_write:
            lat, lng = content.get("lat"), content.get("lng")
            if lat is None or lng is None:
                return
            warnings = await self._save_point(self.ride_id, lat, lng)
            await self.channel_layer.group_send(
                self.group,
                {"type": "location.message", "lat": lat, "lng": lng},
            )
            for kind, message in warnings:
                await self.channel_layer.group_send(
                    self.group,
                    {"type": "alert.message", "alert": {"kind": kind, "message": message}},
                )

    # --- group event handlers ---
    async def location_message(self, event):
        await self.send_json({"type": "location", "lat": event["lat"], "lng": event["lng"]})

    async def alert_message(self, event):
        await self.send_json({"type": "alert", "alert": event["alert"]})

    async def status_message(self, event):
        await self.send_json({"type": "status", "status": event["status"]})

    # --- helpers ---
    def _query_param(self, key):
        qs = self.scope.get("query_string", b"").decode()
        for part in qs.split("&"):
            if part.startswith(f"{key}="):
                return part.split("=", 1)[1]
        return None

    @sync_to_async
    def _get_ride(self, ride_id):
        from .models import Ride

        return Ride.objects.filter(pk=ride_id).first()

    @sync_to_async
    def _last_point(self, ride):
        pt = ride.tracking_points.order_by("-timestamp").first()
        return {"lat": pt.latitude, "lng": pt.longitude} if pt else None

    @sync_to_async
    def _can_write(self, ride, user):
        return bool(
            user
            and user.is_authenticated
            and ride.driver_id == user.id
        )

    @sync_to_async
    def _can_read(self, ride, user, token):
        if user and user.is_authenticated:
            if ride.rider_id == user.id or getattr(user, "is_platform_admin", False):
                return True
        if token and str(ride.share_token) == token:
            return True
        return False

    @sync_to_async
    def _save_point(self, ride_id, lat, lng):
        from .models import Ride, RideTracking
        from .utils import evaluate_safety
        from .services import raise_safety_alert

        ride = Ride.objects.get(pk=ride_id)
        RideTracking.objects.create(ride=ride, latitude=lat, longitude=lng)
        # Cache on the driver profile for quick map reads.
        if ride.driver and hasattr(ride.driver, "driver_profile"):
            dp = ride.driver.driver_profile
            dp.current_lat, dp.current_lng = lat, lng
            dp.save(update_fields=["current_lat", "current_lng"])
        warnings = evaluate_safety(ride, lat, lng)
        for kind, message in warnings:
            raise_safety_alert(ride, kind, message, lat, lng)
        return warnings


class AdminAlertsConsumer(AsyncJsonWebsocketConsumer):
    """Live feed of all emergency alerts for the admin emergency center."""

    async def connect(self):
        user = self.scope["user"]
        if not (user and user.is_authenticated and getattr(user, "is_platform_admin", False)):
            await self.close()
            return
        await self.channel_layer.group_add(ADMIN_ALERTS_GROUP, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        await self.channel_layer.group_discard(ADMIN_ALERTS_GROUP, self.channel_name)

    async def alert_message(self, event):
        await self.send_json({"type": "alert", "alert": event["alert"]})


class DriverRequestsConsumer(AsyncJsonWebsocketConsumer):
    """Live feed of incoming ride requests for one driver's dashboard."""

    async def connect(self):
        user = self.scope["user"]
        if not (user and user.is_authenticated and getattr(user, "is_driver", False)):
            await self.close()
            return
        self.group = f"driver_{user.id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def request_message(self, event):
        await self.send_json({"type": "request", "request": event["request"]})
