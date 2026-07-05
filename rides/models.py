import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Ride(models.Model):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        ACCEPTED = "accepted", "Accepted"
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        REJECTED = "rejected", "Rejected"

    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="rides_as_rider"
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rides_as_driver",
    )

    pickup_location = models.CharField(max_length=255)
    pickup_lat = models.FloatField()
    pickup_lng = models.FloatField()

    destination = models.CharField(max_length=255)
    destination_lat = models.FloatField()
    destination_lng = models.FloatField()

    # Encoded/serialised planned route (list of [lat, lng]) for deviation checks.
    planned_route = models.JSONField(default=list, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    eta_minutes = models.PositiveIntegerField(null=True, blank=True)

    # Pricing + cancellation
    distance_km = models.FloatField(null=True, blank=True)
    fare = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True, default="")

    # Public, unguessable token for trip sharing (no account required to view).
    share_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Ride #{self.pk} {self.pickup_location} -> {self.destination} [{self.status}]"

    @property
    def is_active(self):
        return self.status in (self.Status.ACCEPTED, self.Status.ONGOING)

    @property
    def last_tracking(self):
        return self.tracking_points.order_by("-timestamp").first()

    def has_been_rated(self):
        return hasattr(self, "rating")


class RideTracking(models.Model):
    """Append-only GPS breadcrumb stream for a ride."""

    ride = models.ForeignKey(Ride, on_delete=models.CASCADE, related_name="tracking_points")
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["timestamp"]
        indexes = [models.Index(fields=["ride", "timestamp"])]

    def __str__(self):
        return f"({self.latitude:.5f}, {self.longitude:.5f}) @ {self.timestamp:%H:%M:%S}"


class EmergencyAlert(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    class Kind(models.TextChoices):
        SOS = "sos", "SOS Button"
        ROUTE_DEVIATION = "route_deviation", "Route Deviation"
        STATIONARY = "stationary", "Vehicle Stationary"
        ETA_EXCEEDED = "eta_exceeded", "ETA Exceeded"
        INCIDENT = "incident", "Reported Incident"

    ride = models.ForeignKey(
        Ride, on_delete=models.CASCADE, related_name="emergency_alerts", null=True, blank=True
    )
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="emergency_alerts"
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts_raised",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.SOS)
    location = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=14, choices=Status.choices, default=Status.ACTIVE)
    created_at = models.DateTimeField(default=timezone.now)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} alert #{self.pk} [{self.status}]"


class IncidentReport(models.Model):
    """Rider/driver report about a trip (harassment, unsafe driving, etc.)."""

    ride = models.ForeignKey(
        Ride, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports"
    )
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reports_filed"
    )
    category = models.CharField(max_length=80, default="Other")
    description = models.TextField()
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Report #{self.pk} by {self.reporter.name}"


class Rating(models.Model):
    ride = models.OneToOneField(Ride, on_delete=models.CASCADE, related_name="rating")
    rider = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ratings_given"
    )
    driver = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="driver_ratings"
    )
    score = models.PositiveSmallIntegerField()  # 1..5
    review = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.score}* for {self.driver.name}"
