from django.contrib import admin

from .models import EmergencyAlert, IncidentReport, Rating, Ride, RideTracking


@admin.register(Ride)
class RideAdmin(admin.ModelAdmin):
    list_display = ("id", "rider", "driver", "status", "pickup_location", "destination", "created_at")
    list_filter = ("status",)
    search_fields = ("rider__name", "driver__name", "pickup_location", "destination")
    readonly_fields = ("share_token", "created_at")


@admin.register(RideTracking)
class RideTrackingAdmin(admin.ModelAdmin):
    list_display = ("ride", "latitude", "longitude", "timestamp")
    list_filter = ("ride",)


@admin.register(EmergencyAlert)
class EmergencyAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "rider", "ride", "status", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("rider__name",)


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ("id", "reporter", "category", "resolved", "created_at")
    list_filter = ("resolved", "category")


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ("id", "driver", "rider", "score", "created_at")
    list_filter = ("score",)
