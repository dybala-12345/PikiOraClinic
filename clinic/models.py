# models for the clinic
# doctor -> weekly schedules and appointment slots
# slot -> appointments (only 1 active booking per slot)
# patient -> appointments and notifications

from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Exists, F, OuterRef, Q
from django.urls import reverse
from django.utils import timezone

from accounts.models import phone_validator


class TimeStampedModel(models.Model):
    # adds created/updated dates to other models

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# doctors + weekly schedules
class Doctor(TimeStampedModel):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    specialisation = models.CharField(max_length=120, default="General Practitioner")
    qualifications = models.CharField(max_length=200, blank=True, help_text="e.g. MBChB, FRNZCGP")
    bio = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    room = models.CharField("Consultation room", max_length=30, blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive doctors are hidden from patients and cannot be booked.",
    )

    class Meta:
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"Dr {self.first_name} {self.last_name}"

    @property
    def initials(self):
        return f"{self.first_name[:1]}{self.last_name[:1]}".upper()

    def get_absolute_url(self):
        return reverse("clinic:doctor_detail", args=[self.pk])


class DoctorSchedule(models.Model):
    # a doctor's weekly session e.g. monday 9-12

    class Weekday(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="schedules")
    weekday = models.IntegerField(choices=Weekday.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_minutes = models.PositiveSmallIntegerField(
        "Appointment length (minutes)",
        default=15,
        help_text="Used when generating appointment slots from this schedule.",
    )

    class Meta:
        ordering = ["weekday", "start_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "weekday", "start_time"],
                name="unique_schedule_start_per_doctor_day",
                violation_error_message="This doctor already has a session starting then on that day.",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="schedule_end_after_start",
            ),
        ]

    def __str__(self):
        return (
            f"{self.doctor} - {self.get_weekday_display()} "
            f"{self.start_time:%H:%M}-{self.end_time:%H:%M}"
        )

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after the start time."})
        if self.slot_minutes is not None and not 5 <= self.slot_minutes <= 120:
            raise ValidationError({"slot_minutes": "Choose a length between 5 and 120 minutes."})
        if self.doctor_id and self.start_time and self.end_time and self.weekday is not None:
            overlapping = DoctorSchedule.objects.filter(
                doctor_id=self.doctor_id,
                weekday=self.weekday,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError("This session overlaps another session for this doctor on the same day.")


# slots
class AppointmentSlotQuerySet(models.QuerySet):
    def upcoming(self):
        # slots that haven't started yet (nz time)
        now = timezone.localtime()
        return self.filter(
            Q(date__gt=now.date()) | Q(date=now.date(), start_time__gt=now.time())
        )

    def with_booking_status(self):
        # adds has_booking = True/False to each slot
        active_booking = Appointment.objects.filter(
            slot=OuterRef("pk"), status=Appointment.Status.BOOKED
        )
        return self.annotate(has_booking=Exists(active_booking))

    def available(self):
        # free future slots (slot open, doctor active, not booked)
        return (
            self.upcoming()
            .filter(is_active=True, doctor__is_active=True)
            .with_booking_status()
            .filter(has_booking=False)
        )


class AppointmentSlot(TimeStampedModel):
    # one bookable time e.g. 14 oct 10:00-10:15

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name="slots")
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(
        "Open for booking",
        default=True,
        help_text="Untick to block this slot (e.g. doctor unavailable).",
    )

    objects = AppointmentSlotQuerySet.as_manager()

    class Meta:
        ordering = ["date", "start_time", "doctor__last_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                name="unique_slot_per_doctor_time",
                violation_error_message="This doctor already has a slot starting at that time.",
            ),
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="slot_end_after_start",
            ),
        ]
        indexes = [models.Index(fields=["date", "start_time"], name="slot_date_time_idx")]

    def __str__(self):
        return f"{self.doctor} - {self.date:%a %d %b %Y} {self.start_time:%H:%M}"

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after the start time."})
        if self.doctor_id and self.date and self.start_time and self.end_time:
            overlapping = AppointmentSlot.objects.filter(
                doctor_id=self.doctor_id,
                date=self.date,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time,
            ).exclude(pk=self.pk)
            if overlapping.exists():
                raise ValidationError("This slot overlaps an existing slot for the same doctor.")

    # helpers for the views/templates
    @property
    def start_datetime(self):
        return timezone.make_aware(datetime.combine(self.date, self.start_time))

    @property
    def is_past(self):
        return self.start_datetime <= timezone.now()

    @property
    def is_booked(self):
        if hasattr(self, "has_booking"):  # set by with_booking_status()
            return self.has_booking
        return self.appointments.filter(status=Appointment.Status.BOOKED).exists()

    @property
    def duration_minutes(self):
        start = datetime.combine(self.date, self.start_time)
        end = datetime.combine(self.date, self.end_time)
        return int((end - start) / timedelta(minutes=1))

    @property
    def label(self):
        return f"{self.date:%a %d %b %Y}, {self.start_time:%H:%M}-{self.end_time:%H:%M}"


# appointments
class AppointmentQuerySet(models.QuerySet):
    def booked(self):
        return self.filter(status=Appointment.Status.BOOKED)

    def upcoming(self):
        now = timezone.localtime()
        return self.filter(
            Q(slot__date__gt=now.date())
            | Q(slot__date=now.date(), slot__start_time__gt=now.time())
        )

    def past(self):
        now = timezone.localtime()
        return self.filter(
            Q(slot__date__lt=now.date())
            | Q(slot__date=now.date(), slot__start_time__lte=now.time())
        )


class Appointment(TimeStampedModel):
    class Status(models.TextChoices):
        BOOKED = "booked", "Booked"
        CANCELLED = "cancelled", "Cancelled"
        COMPLETED = "completed", "Completed"

    patient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    # PROTECT so a slot with appointment history can't be deleted by mistake
    slot = models.ForeignKey(AppointmentSlot, on_delete=models.PROTECT, related_name="appointments")
    reason = models.TextField("Reason for visit", max_length=500)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.BOOKED)
    admin_notes = models.TextField("Staff notes", blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    objects = AppointmentQuerySet.as_manager()

    class Meta:
        ordering = ["slot__date", "slot__start_time"]
        constraints = [
            # stops double booking in the database itself - only 1 'booked' appointment per slot
            # cancelled ones are kept for history and don't count
            models.UniqueConstraint(
                fields=["slot"],
                condition=Q(status="booked"),
                name="one_active_booking_per_slot",
                violation_error_message="This time slot has already been booked.",
            ),
        ]

    def __str__(self):
        return f"{self.patient.get_full_name() or self.patient.username} with {self.slot}"

    @property
    def doctor(self):
        return self.slot.doctor

    @property
    def is_active_booking(self):
        return self.status == self.Status.BOOKED

    @property
    def can_be_changed(self):
        # patient can only edit/cancel if it's still booked and in the future
        return self.is_active_booking and not self.slot.is_past

    @property
    def status_badge(self):
        # bootstrap colour for the status label
        return {
            self.Status.BOOKED: "success",
            self.Status.CANCELLED: "secondary",
            self.Status.COMPLETED: "info",
        }.get(self.status, "light")

    def get_absolute_url(self):
        return reverse("clinic:appointment_detail", args=[self.pk])


# notifications
class Notification(models.Model):
    # message shown to the patient e.g. booking confirmed

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    title = models.CharField(max_length=120)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user}: {self.title}"
