"""Patient-facing forms for booking and changing appointments."""

from django import forms
from django.db.models import Q

from core.forms import BootstrapFormMixin

from .models import AppointmentSlot, Doctor


class SlotChoiceField(forms.ModelChoiceField):
    """Shows slots as 'Mon 14 Oct 2026, 10:00-10:15' instead of the default text."""

    def label_from_instance(self, obj):
        return obj.label


def clean_reason_text(value):
    value = (value or "").strip()
    if len(value) < 3:
        raise forms.ValidationError("Please describe the reason for your visit.")
    return value


class BookingForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(
        label="Reason for visit",
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "e.g. Repeat prescription, flu symptoms, check-up"}),
    )

    def clean_reason(self):
        return clean_reason_text(self.cleaned_data.get("reason"))


class AppointmentEditForm(BootstrapFormMixin, forms.Form):
    """Lets a patient move their appointment to another free slot with the same doctor."""

    slot = SlotChoiceField(queryset=AppointmentSlot.objects.none(), label="Date and time")
    reason = forms.CharField(
        label="Reason for visit",
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, appointment, **kwargs):
        super().__init__(*args, **kwargs)
        self.appointment = appointment
        # Free future slots for the same doctor, plus the slot already held.
        free_slots = AppointmentSlot.objects.filter(doctor=appointment.slot.doctor).available()
        self.fields["slot"].queryset = AppointmentSlot.objects.filter(
            Q(pk__in=free_slots.values("pk")) | Q(pk=appointment.slot_id)
        ).order_by("date", "start_time")
        self.fields["slot"].initial = appointment.slot_id
        self.fields["reason"].initial = appointment.reason

    def clean_reason(self):
        return clean_reason_text(self.cleaned_data.get("reason"))


class DoctorFilterForm(BootstrapFormMixin, forms.Form):
    """Search box on the public doctors page."""

    q = forms.CharField(required=False, label="Search", widget=forms.TextInput(attrs={"placeholder": "Name or specialisation"}))
    specialisation = forms.ChoiceField(required=False, choices=())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        specialisations = (
            Doctor.objects.filter(is_active=True)
            .order_by("specialisation")
            .values_list("specialisation", flat=True)
            .distinct()
        )
        self.fields["specialisation"].choices = [("", "All specialisations")] + [
            (s, s) for s in specialisations
        ]
