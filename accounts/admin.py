from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import DriverProfile, TrustedContact, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
<<<<<<< HEAD
    list_display = ("email", "name", "role", "status", "is_active", "is_staff", "created_at")
    list_filter = ("role", "status", "is_active", "is_staff")
=======
    list_display = ("email", "name", "role", "status", "is_staff", "created_at")
    list_filter = ("role", "status", "is_staff")
>>>>>>> 3b4da265b9e6343f66681dd946ef6089191e86dd
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
