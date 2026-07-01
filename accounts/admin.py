from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import DriverProfile, TrustedContact, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "name", "role", "status", "is_staff", "created_at")
    list_filter = ("role", "status", "is_staff")
    search_fields = ("email", "name", "phone")
    ordering = ("-created_at",)
    fieldsets = BaseUserAdmin.fieldsets + (
        ("SafeDrive", {"fields": ("name", "phone", "role", "status", "created_at")}),
    )
    readonly_fields = ("created_at",)


@admin.register(DriverProfile)
class DriverProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "vehicle_number", "vehicle_type", "verification_status", "is_online")
    list_filter = ("verification_status", "is_online")
    search_fields = ("user__name", "user__email", "vehicle_number", "license_number")


@admin.register(TrustedContact)
class TrustedContactAdmin(admin.ModelAdmin):
    list_display = ("name", "rider", "phone", "email")
    search_fields = ("name", "phone", "rider__name")
