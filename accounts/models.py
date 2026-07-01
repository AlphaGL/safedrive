from urllib.parse import quote

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """Custom user supporting three roles: rider, driver, admin.

    We keep Django's username field (used internally) but authenticate by
    email. `name` is the human display name from the spec.
    """

    class Role(models.TextChoices):
        RIDER = "rider", "Rider"
        DRIVER = "driver", "Driver"
        ADMIN = "admin", "Administrator"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended"
        PENDING = "pending", "Pending"

    name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.RIDER)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    avatar_url = models.URLField(blank=True, default="")
    created_at = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "name"]

    def __str__(self):
        return f"{self.name or self.username} ({self.role})"

    @property
    def is_rider(self):
        return self.role == self.Role.RIDER

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER

    @property
    def is_platform_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def avatar(self):
        """Profile photo if set, otherwise a clean generated initials avatar."""
        if self.avatar_url:
            return self.avatar_url
        label = quote(self.name or self.email or "User")
        return (
            f"https://ui-avatars.com/api/?name={label}"
            "&background=19c37d&color=06120c&bold=true&size=128"
        )


class DriverProfile(models.Model):
    class Verification(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        SUSPENDED = "suspended", "Suspended"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="driver_profile")
    license_number = models.CharField(max_length=60, blank=True)
    vehicle_type = models.CharField(max_length=60, blank=True)
    vehicle_number = models.CharField(max_length=30, blank=True)
    verification_status = models.CharField(
        max_length=10, choices=Verification.choices, default=Verification.PENDING
    )

    # Uploaded documents
    license_document = models.FileField(upload_to="documents/licenses/", blank=True, null=True)
    id_card = models.FileField(upload_to="documents/id_cards/", blank=True, null=True)
    vehicle_document = models.FileField(upload_to="documents/vehicles/", blank=True, null=True)

    # Live location cache for quick map reads (authoritative stream is RideTracking)
    current_lat = models.FloatField(blank=True, null=True)
    current_lng = models.FloatField(blank=True, null=True)
    is_online = models.BooleanField(default=False)
    vehicle_image_url = models.URLField(blank=True, default="")

    def __str__(self):
        return f"DriverProfile<{self.user.name}> [{self.verification_status}]"

    @property
    def is_approved(self):
        return self.verification_status == self.Verification.APPROVED

    @property
    def average_rating(self):
        agg = self.user.driver_ratings.aggregate(models.Avg("score"))
        return round(agg["score__avg"], 1) if agg["score__avg"] else None

    @property
    def vehicle_image(self):
        return self.vehicle_image_url or (
            "https://images.unsplash.com/photo-1549317661-bd32c8ce0db2"
            "?auto=format&fit=crop&w=600&q=80"
        )


class TrustedContact(models.Model):
    rider = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trusted_contacts")
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} -> {self.rider.name}"
