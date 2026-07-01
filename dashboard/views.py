from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import DriverProfile, User
from rides.models import EmergencyAlert, IncidentReport, Rating, Ride


def admin_required(view):
    def check(user):
        return user.is_authenticated and user.is_platform_admin
    return user_passes_test(check, login_url="accounts:login")(view)


@admin_required
def admin_home(request):
    active_statuses = [Ride.Status.ACCEPTED, Ride.Status.ONGOING]
    stats = {
        "total_riders": User.objects.filter(role=User.Role.RIDER).count(),
        "total_drivers": User.objects.filter(role=User.Role.DRIVER).count(),
        "total_trips": Ride.objects.count(),
        "active_trips": Ride.objects.filter(status__in=active_statuses).count(),
        "emergency_alerts": EmergencyAlert.objects.filter(
            status=EmergencyAlert.Status.ACTIVE
        ).count(),
        "pending_verifications": DriverProfile.objects.filter(
            verification_status=DriverProfile.Verification.PENDING
        ).count(),
    }
    recent_alerts = EmergencyAlert.objects.select_related("rider", "ride")[:8]
    active_rides = Ride.objects.filter(status__in=active_statuses).select_related(
        "rider", "driver"
    )[:10]
    return render(
        request,
        "dashboard/admin_home.html",
        {"stats": stats, "recent_alerts": recent_alerts, "active_rides": active_rides},
    )


# --- Driver management ---
@admin_required
def driver_management(request):
    profiles = DriverProfile.objects.select_related("user").order_by("verification_status")
    return render(request, "dashboard/driver_management.html", {"profiles": profiles})


@admin_required
@require_POST
def set_driver_status(request, pk, action):
    profile = get_object_or_404(DriverProfile, pk=pk)
    mapping = {
        "approve": DriverProfile.Verification.APPROVED,
        "reject": DriverProfile.Verification.REJECTED,
        "suspend": DriverProfile.Verification.SUSPENDED,
    }
    if action not in mapping:
        messages.error(request, "Unknown action.")
        return redirect("dashboard:driver_management")
    profile.verification_status = mapping[action]
    profile.save(update_fields=["verification_status"])
    # Keep the user account status in sync.
    if action == "approve":
        profile.user.status = User.Status.ACTIVE
    elif action == "suspend":
        profile.user.status = User.Status.SUSPENDED
    profile.user.save(update_fields=["status"])
    messages.success(request, f"Driver {profile.user.name} {action}d.")
    return redirect("dashboard:driver_management")


# --- Ride monitoring ---
@admin_required
def ride_monitoring(request):
    active = Ride.objects.filter(
        status__in=[Ride.Status.ACCEPTED, Ride.Status.ONGOING]
    ).select_related("rider", "driver")
    points = [
        {
            "ride_id": r.id,
            "rider": r.rider.name,
            "driver": r.driver.name if r.driver else "—",
            "lat": (r.last_tracking.latitude if r.last_tracking else r.pickup_lat),
            "lng": (r.last_tracking.longitude if r.last_tracking else r.pickup_lng),
        }
        for r in active
    ]
    return render(
        request,
        "dashboard/ride_monitoring.html",
        {"active_rides": active, "points_json": points},
    )


@admin_required
def trip_logs(request, pk):
    ride = get_object_or_404(Ride, pk=pk)
    return render(
        request,
        "dashboard/trip_logs.html",
        {"ride": ride, "points": ride.tracking_points.all()},
    )


# --- Emergency center ---
@admin_required
def emergency_center(request):
    alerts = EmergencyAlert.objects.select_related("rider", "ride", "ride__driver")
    return render(request, "dashboard/emergency_center.html", {"alerts": alerts})


@admin_required
@require_POST
def update_alert_status(request, pk, status):
    alert = get_object_or_404(EmergencyAlert, pk=pk)
    valid = {s for s, _ in EmergencyAlert.Status.choices}
    if status not in valid:
        messages.error(request, "Invalid status.")
        return redirect("dashboard:emergency_center")
    alert.status = status
    if status == EmergencyAlert.Status.RESOLVED:
        alert.resolved_at = timezone.now()
    alert.save()
    messages.success(request, f"Alert #{alert.id} marked {status}.")
    return redirect("dashboard:emergency_center")


# --- User management ---
@admin_required
def manage_riders(request):
    riders = User.objects.filter(role=User.Role.RIDER)
    return render(request, "dashboard/manage_riders.html", {"riders": riders})


@admin_required
def manage_drivers(request):
    drivers = User.objects.filter(role=User.Role.DRIVER).select_related("driver_profile")
    return render(request, "dashboard/manage_drivers.html", {"drivers": drivers})


@admin_required
@require_POST
def toggle_user_suspension(request, pk):
    user = get_object_or_404(User, pk=pk)
    user.status = (
        User.Status.ACTIVE if user.status == User.Status.SUSPENDED else User.Status.SUSPENDED
    )
    user.save(update_fields=["status"])
    messages.success(request, f"{user.name} is now {user.status}.")
    return redirect(request.META.get("HTTP_REFERER", "dashboard:manage_riders"))


@admin_required
def ratings_list(request):
    ratings = Rating.objects.select_related("rider", "driver", "ride")
    return render(request, "dashboard/ratings.html", {"ratings": ratings})


@admin_required
def reports_list(request):
    reports = IncidentReport.objects.select_related("reporter", "ride")
    return render(request, "dashboard/reports.html", {"reports": reports})


@admin_required
@require_POST
def resolve_report(request, pk):
    report = get_object_or_404(IncidentReport, pk=pk)
    report.resolved = True
    report.save(update_fields=["resolved"])
    messages.success(request, "Report marked resolved.")
    return redirect("dashboard:reports_list")
