from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm
from django.db.models import Q
from django.utils import timezone

from accounts.forms import PatientRegistrationForm
from clinic.forms import SlotChoiceField
from clinic.models import Appointment, AppointmentSlot, Doctor, DoctorSchedule
from core.forms import BootstrapFormMixin, DateInput, TimeInput

User = get_user_model()

MAX_GENERATE_DAYS = 90


# doctors
class DoctorForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = Doctor
        fields = [
            "first_name",
            "last_name",
            "specialisation",
            "qualifications",
            "email",
            "phone",
            "room",
            "bio",
            "is_active",
        ]
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}


class DoctorScheduleForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = DoctorSchedule
        fields = ["weekday", "start_time", "end_time", "slot_minutes"]
        widgets = {"start_time": TimeInput(), "end_time": TimeInput()}

    def __init__(self, *args, doctor=None, **kwargs):
        super().__init__(*args, **kwargs)
        if doctor is not None:
            # set the doctor first so the overlap check works
            self.instance.doctor = doctor


# slots
class SlotForm(BootstrapFormMixin, forms.ModelForm):
    class Meta:
        model = AppointmentSlot
        fields = ["doctor", "date", "start_time", "end_time", "is_active"]
        widgets = {"date": DateInput(), "start_time": TimeInput(), "end_time": TimeInput()}

    def clean_date(self):
        value = self.cleaned_data["date"]
        if self.instance.pk is None and value < timezone.localdate():
            raise forms.ValidationError("New slots must be today or in the future.")
        return value


class GenerateSlotsForm(BootstrapFormMixin, forms.Form):
    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.filter(is_active=True),
        required=False,
        empty_label="All active doctors",
    )
    start_date = forms.DateField(widget=DateInput())
    end_date = forms.DateField(widget=DateInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["start_date"].initial = today
        self.fields["end_date"].initial = today + timedelta(days=13)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end:
            if start < timezone.localdate():
                self.add_error("start_date", "Start date cannot be in the past.")
            if end < start:
                self.add_error("end_date", "End date must be on or after the start date.")
            elif (end - start).days >= MAX_GENERATE_DAYS:
                self.add_error("end_date", f"Generate at most {MAX_GENERATE_DAYS} days at a time.")
        return cleaned


class SlotFilterForm(BootstrapFormMixin, forms.Form):
    doctor = forms.ModelChoiceField(queryset=Doctor.objects.all(), required=False, empty_label="All doctors")
    date = forms.DateField(required=False, widget=DateInput())
    status = forms.ChoiceField(
        required=False,
        choices=[("", "Any status"), ("available", "Available"), ("booked", "Booked"), ("closed", "Closed")],
    )
    show_past = forms.BooleanField(required=False, label="Include past slots")


# appointments
class AdminAppointmentForm(BootstrapFormMixin, forms.Form):
    # admin can change the time, status or notes of any appointment

    slot = SlotChoiceField(queryset=AppointmentSlot.objects.none(), label="Doctor, date and time")
    status = forms.ChoiceField(choices=Appointment.Status.choices)
    reason = forms.CharField(label="Reason for visit", max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    admin_notes = forms.CharField(label="Staff notes", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, appointment, **kwargs):
        super().__init__(*args, **kwargs)
        free = AppointmentSlot.objects.available().values("pk")
        self.fields["slot"].queryset = (
            AppointmentSlot.objects.filter(Q(pk__in=free) | Q(pk=appointment.slot_id))
            .select_related("doctor")
            .order_by("date", "start_time")
        )
        self.fields["slot"].label_from_instance = lambda s: f"{s.doctor.full_name} - {s.label}"
        self.initial.update(
            {
                "slot": appointment.slot_id,
                "status": appointment.status,
                "reason": appointment.reason,
                "admin_notes": appointment.admin_notes,
            }
        )


class AppointmentFilterForm(BootstrapFormMixin, forms.Form):
    q = forms.CharField(required=False, label="Patient", widget=forms.TextInput(attrs={"placeholder": "Patient name, username or e-mail"}))
    doctor = forms.ModelChoiceField(queryset=Doctor.objects.all(), required=False, empty_label="All doctors")
    status = forms.ChoiceField(required=False, choices=[("", "Any status")] + list(Appointment.Status.choices))
    date_from = forms.DateField(required=False, label="From", widget=DateInput())
    date_to = forms.DateField(required=False, label="To", widget=DateInput())


# patients
class AdminPatientCreateForm(PatientRegistrationForm):
    # admin can make a patient account for someone e.g. if they phone in
    pass


class AdminUserAccountForm(BootstrapFormMixin, forms.ModelForm):
    # patient login details the admin can edit

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "is_active"]
        help_texts = {"is_active": "Untick to block this patient from logging in."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Another account already uses this e-mail address.")
        return email


class AdminSetPasswordForm(BootstrapFormMixin, SetPasswordForm):
    # admin sets a new password if a patient is locked out
    pass
