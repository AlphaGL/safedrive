from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.admin_home, name="admin_home"),

    # Driver management
    path("drivers/", views.driver_management, name="driver_management"),
    path("drivers/<int:pk>/<str:action>/", views.set_driver_status, name="set_driver_status"),

    # Ride monitoring
    path("monitoring/", views.ride_monitoring, name="ride_monitoring"),
    path("monitoring/<int:pk>/logs/", views.trip_logs, name="trip_logs"),

    # Emergency center
    path("emergency/", views.emergency_center, name="emergency_center"),
    path("emergency/<int:pk>/<str:status>/", views.update_alert_status, name="update_alert_status"),

    # User management
    path("users/riders/", views.manage_riders, name="manage_riders"),
    path("users/drivers/", views.manage_drivers, name="manage_drivers"),
    path("users/<int:pk>/toggle/", views.toggle_user_suspension, name="toggle_user_suspension"),
    path("ratings/", views.ratings_list, name="ratings_list"),
    path("reports/", views.reports_list, name="reports_list"),
    path("reports/<int:pk>/resolve/", views.resolve_report, name="resolve_report"),
]
