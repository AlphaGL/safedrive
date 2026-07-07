from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("login/", views.SafeLoginView.as_view(), name="login"),
    path("logout/", views.SafeLogoutView.as_view(), name="logout"),
    path("go/", views.redirect_dashboard, name="redirect_dashboard"),
    path("profile/", views.profile, name="profile"),
    path("trusted-contacts/", views.trusted_contacts, name="trusted_contacts"),
    path("trusted-contacts/<int:pk>/delete/", views.delete_trusted_contact, name="delete_trusted_contact"),
    path("driver/verification/", views.driver_verification, name="driver_verification"),
]
