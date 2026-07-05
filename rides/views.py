import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import DriverProfile, User

from .forms import IncidentReportForm, RatingForm, RideRequestForm
from .models import EmergencyAlert, Rating, Ride
from .services import broadcast_ride_status, create_sos, notify_driver_of_request
from .utils import (
    build_straight_route,
    estimate_eta_minutes,
    estimate_fare,
    haversine_m,
)


# --------------------------------------------------------------------------- #
# Rider
# --------------------------------------------------------------------------- #
@login_required
def rider_dashboard(request):
    rides = request.user.rides_as_rider.all()[:5]
    active = request.user.rides_as_rider.filter(
        status__in=[Ride.Status.REQUESTED, Ride.Status.ACCEPTED, Ride.Status.ONGOING]
    ).first()
    return render(
        request,
        "rides/rider_dashboard.html",
        {"rides": rides, "active_ride": active},
    )


@login_required
def request_ride(request):
    # Block a new request if rider already has an active one.
    active = request.user.rides_as_rider.filter(
        status__in=[Ride.Status.REQUESTED, Ride.Status.ACCEPTED, Ride.Status.ONGOING]
    ).first()
    if active:
        messages.info(request, "You already have an active ride.")
        return redirect("rides:track", pk=active.pk)

    if request.method == "POST":
        form = RideRequestForm(request.POST)
        if form.is_valid():
            ride = form.save(commit=False)
            ride.rider = request.user

            # The rider books a specific driver they picked from the list.
            driver_id = request.POST.get("driver_id")
            driver = None
            if driver_id:
                driver = User.objects.filter(
                    pk=driver_id,
                    role=User.Role.DRIVER,
                    status=User.Status.ACTIVE,
                    driver_profile__verification_status=DriverProfile.Verification.APPROVED,
                ).first()
            if not driver:
                messages.error(request, "Please choose an available driver to book.")
                return render(request, "rides/request_ride.html", {"form": form})
            ride.driver = driver

            ride.planned_route = build_straight_route(
                (ride.pickup_lat, ride.pickup_lng),
                (ride.destination_lat, ride.destination_lng),
            )
            distance = haversine_m(
                ride.pickup_lat, ride.pickup_lng,
                ride.destination_lat, ride.destination_lng,
            )
            ride.distance_km = round(distance / 1000, 1)
            ride.eta_minutes = estimate_eta_minutes(distance)
            ride.fare = estimate_fare(distance, ride.eta_minutes)
            ride.status = Ride.Status.REQUESTED
            ride.save()
            notify_driver_of_request(ride)
            messages.success(
                request, f"Request sent to {driver.name}. Waiting for them to accept…"
            )
            return redirect("rides:track", pk=ride.pk)
    else:
        form = RideRequestForm()
    return render(request, "rides/request_ride.html", {"form": form})


@login_required
def available_drivers(request):
    """JSON list of verified drivers who are ONLINE and free, ranked for safety.

    Safety-first ordering: higher-rated, more-experienced drivers surface first,
    then nearest. Offline, unverified, suspended or busy drivers never appear.
    """
    lat = float(request.GET.get("lat", 0))
    lng = float(request.GET.get("lng", 0))
    # Drivers currently tied up on a live trip can't be booked.
    busy_driver_ids = Ride.objects.filter(
        status__in=[Ride.Status.ACCEPTED, Ride.Status.ONGOING]
    ).values_list("driver_id", flat=True)
    drivers = (
        DriverProfile.objects.filter(
            verification_status=DriverProfile.Verification.APPROVED,
            user__status=User.Status.ACTIVE,
            is_online=True,  # only online drivers
        )
        .exclude(user_id__in=busy_driver_ids)
        .select_related("user")
    )
    data = []
    for dp in drivers:
        d_lat = dp.current_lat if dp.current_lat is not None else lat + 0.01
        d_lng = dp.current_lng if dp.current_lng is not None else lng + 0.01
        distance = haversine_m(lat, lng, d_lat, d_lng) if lat and lng else None
        rating = dp.average_rating
        trips = dp.user.rides_as_driver.filter(status=Ride.Status.COMPLETED).count()
        # A simple safety score: rating (0-5) weighted with experience.
        safety_score = round((rating or 4.0) + min(trips, 50) / 50, 2)
        data.append(
            {
                "id": dp.user_id,
                "name": dp.user.name,
                "vehicle": f"{dp.vehicle_type} · {dp.vehicle_number}",
                "rating": rating,
                "trips": trips,
                "safety_score": safety_score,
                "verified": True,
                "avatar": dp.user.avatar,
                "vehicle_image": dp.vehicle_image,
                "lat": d_lat,
                "lng": d_lng,
                "distance_m": round(distance) if distance else None,
            }
        )
    # Safety first (higher score), then nearest.
    data.sort(key=lambda d: (-d["safety_score"], d["distance_m"] is None, d["distance_m"] or 0))
    return JsonResponse({"drivers": data})


@login_required
def fare_estimate(request):
    """Return distance / ETA / fare for a pickup→destination pair."""
    try:
        plat = float(request.GET["plat"]); plng = float(request.GET["plng"])
        dlat = float(request.GET["dlat"]); dlng = float(request.GET["dlng"])
    except (KeyError, ValueError):
        return JsonResponse({"error": "invalid coordinates"}, status=400)
    distance = haversine_m(plat, plng, dlat, dlng)
    eta = estimate_eta_minutes(distance)
    fare = estimate_fare(distance, eta)
    return JsonResponse(
        {"distance_km": round(distance / 1000, 1), "eta_minutes": eta, "fare": fare}
    )


@login_required
def track_ride(request, pk):
    ride = get_object_or_404(Ride, pk=pk)
    if not (ride.rider_id == request.user.id or ride.driver_id == request.user.id
            or request.user.is_platform_admin):
        messages.error(request, "You cannot view this ride.")
        return redirect("accounts:redirect_dashboard")
    return render(
        request,
        "rides/track.html",
        {
            "ride": ride,
            "is_driver": ride.driver_id == request.user.id,
            "planned_route_json": json.dumps(ride.planned_route),
        },
    )


@login_required
@require_POST
def sos(request, pk):
    ride = get_object_or_404(Ride, pk=pk, rider=request.user)
    lat = request.POST.get("lat") or None
    lng = request.POST.get("lng") or None
    location = request.POST.get("location", "")
    alert, notified = create_sos(
        ride, request.user,
        lat=float(lat) if lat else None,
        lng=float(lng) if lng else None,
        location=location,
        raised_by=request.user,
    )
    return JsonResponse(
        {"ok": True, "alert_id": alert.id, "contacts_notified": notified}
    )


@login_required
@require_POST
def cancel_ride(request, pk):
    """Rider cancels an in-progress ride. A reason is required."""
    ride = get_object_or_404(Ride, pk=pk, rider=request.user)
    if ride.status in (
        Ride.Status.COMPLETED, Ride.Status.CANCELLED, Ride.Status.REJECTED
    ):
        messages.error(request, "This ride can no longer be cancelled.")
        return redirect("rides:trip_history")
    reason = request.POST.get("reason", "").strip()
    if reason == "Other":
        reason = request.POST.get("reason_other", "").strip() or "Other"
    if not reason:
        messages.error(request, "Please tell us why you're cancelling.")
        return redirect("rides:track", pk=ride.pk)
    ride.status = Ride.Status.CANCELLED
    ride.cancel_reason = reason
    ride.end_time = timezone.now()
    ride.save()
    ride.emergency_alerts.filter(status=EmergencyAlert.Status.ACTIVE).update(
        status=EmergencyAlert.Status.RESOLVED, resolved_at=timezone.now()
    )
    broadcast_ride_status(ride)
    messages.info(request, "Your ride has been cancelled.")
    return redirect("rides:rider_dashboard")


@login_required
def trip_history(request):
    if request.user.is_driver:
        rides = request.user.rides_as_driver.all()
    else:
        rides = request.user.rides_as_rider.all()
    return render(request, "rides/trip_history.html", {"rides": rides})


@login_required
def rate_ride(request, pk):
    ride = get_object_or_404(Ride, pk=pk, rider=request.user, status=Ride.Status.COMPLETED)
    if ride.has_been_rated():
        messages.info(request, "You already rated this trip.")
        return redirect("rides:trip_history")
    if request.method == "POST":
        form = RatingForm(request.POST)
        if form.is_valid():
            rating = form.save(commit=False)
            rating.ride = ride
            rating.rider = request.user
            rating.driver = ride.driver
            rating.save()
            messages.success(request, "Thanks for rating your driver.")
            return redirect("rides:trip_history")
    else:
        form = RatingForm()
    return render(request, "rides/rate.html", {"form": form, "ride": ride})


@login_required
def report_incident(request, pk=None):
    ride = get_object_or_404(Ride, pk=pk) if pk else None
    if request.method == "POST":
        form = IncidentReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.reporter = request.user
            report.ride = ride
            report.save()
            messages.success(request, "Incident reported. Our safety team will review it.")
            return redirect("accounts:redirect_dashboard")
    else:
        form = IncidentReportForm()
    return render(request, "rides/report.html", {"form": form, "ride": ride})


# --------------------------------------------------------------------------- #
# Trip sharing (public, no account required)
# --------------------------------------------------------------------------- #
def shared_trip(request, token):
    ride = get_object_or_404(Ride, share_token=token)
    driver_profile = getattr(ride.driver, "driver_profile", None) if ride.driver else None
    return render(
        request,
        "rides/shared_trip.html",
        {
            "ride": ride,
            "driver_profile": driver_profile,
            "share_token": str(token),
            "planned_route_json": json.dumps(ride.planned_route),
        },
    )


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #
@login_required
def driver_dashboard(request):
    profile, _ = DriverProfile.objects.get_or_create(user=request.user)
    # Requests this rider directed specifically at THIS driver.
    pending_requests = Ride.objects.filter(
        driver=request.user, status=Ride.Status.REQUESTED
    ).select_related("rider")
    current = request.user.rides_as_driver.filter(
        status__in=[Ride.Status.ACCEPTED, Ride.Status.ONGOING]
    ).first()
    rating = request.user.driver_ratings.aggregate(avg=Avg("score"))["avg"]
    return render(
        request,
        "rides/driver_dashboard.html",
        {
            "profile": profile,
            "pending_requests": pending_requests if profile.is_approved else [],
            "current_ride": current,
            "avg_rating": round(rating, 1) if rating else None,
        },
    )


@login_required
@require_POST
def accept_ride(request, pk):
    profile = get_object_or_404(DriverProfile, user=request.user)
    if not profile.is_approved:
        messages.error(request, "Your account must be verified before accepting rides.")
        return redirect("rides:driver_dashboard")
    ride = get_object_or_404(
        Ride, pk=pk, driver=request.user, status=Ride.Status.REQUESTED
    )
    ride.status = Ride.Status.ACCEPTED
    ride.save()
    broadcast_ride_status(ride)
    messages.success(request, "Ride accepted. Head to the pickup point.")
    return redirect("rides:track", pk=ride.pk)


@login_required
@require_POST
def reject_ride(request, pk):
    ride = get_object_or_404(
        Ride, pk=pk, driver=request.user, status=Ride.Status.REQUESTED
    )
    ride.status = Ride.Status.REJECTED
    ride.save()
    broadcast_ride_status(ride)
    messages.info(request, "Ride request declined. The rider can choose another driver.")
    return redirect("rides:driver_dashboard")


@login_required
@require_POST
def start_ride(request, pk):
    ride = get_object_or_404(Ride, pk=pk, driver=request.user, status=Ride.Status.ACCEPTED)
    ride.status = Ride.Status.ONGOING
    ride.start_time = timezone.now()
    ride.save()
    broadcast_ride_status(ride)
    messages.success(request, "Ride started. Drive safely.")
    return redirect("rides:track", pk=ride.pk)


@login_required
@require_POST
def end_ride(request, pk):
    ride = get_object_or_404(Ride, pk=pk, driver=request.user, status=Ride.Status.ONGOING)
    ride.status = Ride.Status.COMPLETED
    ride.end_time = timezone.now()
    ride.save()
    # Auto-resolve open safety alerts for the trip.
    ride.emergency_alerts.filter(status=EmergencyAlert.Status.ACTIVE).update(
        status=EmergencyAlert.Status.RESOLVED, resolved_at=timezone.now()
    )
    broadcast_ride_status(ride)
    messages.success(request, "Ride completed.")
    return redirect("rides:driver_dashboard")


@login_required
@require_POST
def toggle_online(request):
    profile = get_object_or_404(DriverProfile, user=request.user)
    profile.is_online = not profile.is_online
    profile.save(update_fields=["is_online"])
    return JsonResponse({"is_online": profile.is_online})


@login_required
def driver_ratings(request):
    ratings = request.user.driver_ratings.select_related("rider", "ride")
    avg = ratings.aggregate(avg=Avg("score"))["avg"]
    return render(
        request,
        "rides/driver_ratings.html",
        {"ratings": ratings, "avg_rating": round(avg, 1) if avg else None},
    )
