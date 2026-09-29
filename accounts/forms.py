"""Forms for patient registration and profile management."""

from datetime import date

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from core.forms import BootstrapFormMixin, DateInput

from .models import PatientProfile, phone_validator

User = get_user_model()


def validate_date_of_birth(value):
    if value and value > date.today():
        raise forms.ValidationError("Date of birth cannot be in the future.")
    if value and value.year < 1900:
        raise forms.ValidationError("Please enter a realistic date of birth.")


class PatientRegistrationForm(BootstrapFormMixin, UserCreationForm):
    """Creates a patient login (User) and the matching PatientProfile together."""

    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    email = forms.EmailField(help_text="Booking confirmations are sent to this address.")
    phone = forms.CharField(max_length=20, required=False, validators=[phone_validator])
    date_of_birth = forms.DateField(
        required=False, widget=DateInput(), validators=[validate_date_of_birth]
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this e-mail address already exists.")
        return email

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        user.is_staff = False  # registration can only ever create patients
        if commit:
            user.save()
            PatientProfile.objects.create(
                user=user,
                phone=self.cleaned_data.get("phone", ""),
                date_of_birth=self.cleaned_data.get("date_of_birth"),
            )
        return user


class UserDetailsForm(BootstrapFormMixin, forms.ModelForm):
    """Name and e-mail of an existing user."""

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        clash = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("Another account already uses this e-mail address.")
        return email


class PatientProfileForm(BootstrapFormMixin, forms.ModelForm):
    """Clinic-specific patient details."""

    class Meta:
        model = PatientProfile
        fields = ("phone", "date_of_birth", "address")
        widgets = {"date_of_birth": DateInput()}

    def clean_date_of_birth(self):
        value = self.cleaned_data.get("date_of_birth")
        validate_date_of_birth(value)
        return value
