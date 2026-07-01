from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path("ws/ride/<int:ride_id>/", consumers.RideTrackingConsumer.as_asgi()),
    path("ws/admin/alerts/", consumers.AdminAlertsConsumer.as_asgi()),
    path("ws/driver/requests/", consumers.DriverRequestsConsumer.as_asgi()),
]
