from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import DriverProfile, TrustedContact, User


class RegistrationForm(UserCreationForm):
    name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, required=False)
    role = forms.ChoiceField(
        choices=[(User.Role.RIDER, "Rider"), (User.Role.DRIVER, "Driver")]
    )

    class Meta:
        model = User
        fields = ["name", "email", "phone", "role", "password1", "password2"]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data["email"]
        user.email = self.cleaned_data["email"]
        user.name = self.cleaned_data["name"]
        user.phone = self.cleaned_data["phone"]
        user.role = self.cleaned_data["role"]
        # Drivers start pending until documents are verified
        if user.role == User.Role.DRIVER:
            user.status = User.Status.PENDING
        if commit:
            user.save()
            if user.role == User.Role.DRIVER:
                DriverProfile.objects.get_or_create(user=user)
        return user


class EmailLoginForm(AuthenticationForm):
    """AuthenticationForm uses `username`; we relabel it to Email."""

    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "phone"]


class DriverVerificationForm(forms.ModelForm):
    class Meta:
        model = DriverProfile
        fields = [
            "license_number",
            "vehicle_type",
            "vehicle_number",
            "license_document",
            "id_card",
            "vehicle_document",
        ]


class TrustedContactForm(forms.ModelForm):
    class Meta:
        model = TrustedContact
        fields = ["name", "phone", "email"]
