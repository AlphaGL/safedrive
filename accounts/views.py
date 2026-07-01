from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from .forms import (
    DriverVerificationForm,
    EmailLoginForm,
    ProfileForm,
    RegistrationForm,
    TrustedContactForm,
)
from .models import DriverProfile, TrustedContact, User


def register(request):
    if request.user.is_authenticated:
        return redirect("accounts:redirect_dashboard")
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome to SafeDrive! Your account is ready.")
            return redirect("accounts:redirect_dashboard")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


class SafeLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True


class SafeLogoutView(LogoutView):
    pass


@login_required
def redirect_dashboard(request):
    """Send each role to the correct dashboard after login."""
    user = request.user
    if user.is_platform_admin:
        return redirect("dashboard:admin_home")
    if user.is_driver:
        return redirect("rides:driver_dashboard")
    return redirect("rides:rider_dashboard")


@login_required
def profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/profile.html", {"form": form})


@login_required
def trusted_contacts(request):
    if request.method == "POST":
        form = TrustedContactForm(request.POST)
        if form.is_valid():
            contact = form.save(commit=False)
            contact.rider = request.user
            contact.save()
            messages.success(request, "Trusted contact added.")
            return redirect("accounts:trusted_contacts")
    else:
        form = TrustedContactForm()
    contacts = request.user.trusted_contacts.all()
    return render(
        request,
        "accounts/trusted_contacts.html",
        {"form": form, "contacts": contacts},
    )


@login_required
def delete_trusted_contact(request, pk):
    contact = get_object_or_404(TrustedContact, pk=pk, rider=request.user)
    contact.delete()
    messages.info(request, "Trusted contact removed.")
    return redirect("accounts:trusted_contacts")


@login_required
def driver_verification(request):
    if not request.user.is_driver:
        messages.error(request, "Only drivers can access verification.")
        return redirect("accounts:redirect_dashboard")
    profile_obj, _ = DriverProfile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = DriverVerificationForm(request.POST, request.FILES, instance=profile_obj)
        if form.is_valid():
            profile_obj = form.save(commit=False)
            # Re-submitting docs resets review to pending
            profile_obj.verification_status = DriverProfile.Verification.PENDING
            profile_obj.save()
            messages.success(
                request, "Documents submitted. An administrator will review your account."
            )
            return redirect("accounts:driver_verification")
    else:
        form = DriverVerificationForm(instance=profile_obj)
    return render(
        request,
        "accounts/driver_verification.html",
        {"form": form, "profile": profile_obj},
    )
