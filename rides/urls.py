from django.urls import path

from . import views

app_name = "rides"

urlpatterns = [
    # Rider
    path("rider/", views.rider_dashboard, name="rider_dashboard"),
    path("request/", views.request_ride, name="request_ride"),
    path("available-drivers/", views.available_drivers, name="available_drivers"),
    path("fare-estimate/", views.fare_estimate, name="fare_estimate"),
    path("track/<int:pk>/", views.track_ride, name="track"),
    path("sos/<int:pk>/", views.sos, name="sos"),
    path("cancel/<int:pk>/", views.cancel_ride, name="cancel_ride"),
    path("history/", views.trip_history, name="trip_history"),
    path("rate/<int:pk>/", views.rate_ride, name="rate"),
    path("report/", views.report_incident, name="report"),
    path("report/<int:pk>/", views.report_incident, name="report_ride"),

    # Public trip share (no login)
    path("share/<uuid:token>/", views.shared_trip, name="shared_trip"),

    # Driver
    path("driver/", views.driver_dashboard, name="driver_dashboard"),
    path("driver/accept/<int:pk>/", views.accept_ride, name="accept_ride"),
    path("driver/reject/<int:pk>/", views.reject_ride, name="reject_ride"),
    path("driver/start/<int:pk>/", views.start_ride, name="start_ride"),
    path("driver/end/<int:pk>/", views.end_ride, name="end_ride"),
    path("driver/toggle-online/", views.toggle_online, name="toggle_online"),
    path("driver/ratings/", views.driver_ratings, name="driver_ratings"),
]
