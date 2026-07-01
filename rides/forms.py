from django import forms

from .models import IncidentReport, Rating, Ride


class RideRequestForm(forms.ModelForm):
    class Meta:
        model = Ride
        fields = [
            "pickup_location",
            "pickup_lat",
            "pickup_lng",
            "destination",
            "destination_lat",
            "destination_lng",
        ]
        widgets = {
            "pickup_lat": forms.HiddenInput(),
            "pickup_lng": forms.HiddenInput(),
            "destination_lat": forms.HiddenInput(),
            "destination_lng": forms.HiddenInput(),
        }


class RatingForm(forms.ModelForm):
    score = forms.IntegerField(min_value=1, max_value=5, widget=forms.NumberInput(attrs={"min": 1, "max": 5}))

    class Meta:
        model = Rating
        fields = ["score", "review"]


class IncidentReportForm(forms.ModelForm):
    class Meta:
        model = IncidentReport
        fields = ["category", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}
