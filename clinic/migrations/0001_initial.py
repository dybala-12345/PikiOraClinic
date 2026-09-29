import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

PHONE_VALIDATOR = django.core.validators.RegexValidator(
    message="Enter a valid phone number (digits, spaces, +, - and brackets only).",
    regex="^\\+?[0-9 ()-]{7,20}$",
)


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Doctor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("first_name", models.CharField(max_length=100)),
                ("last_name", models.CharField(max_length=100)),
                ("specialisation", models.CharField(default="General Practitioner", max_length=120)),
                ("qualifications", models.CharField(blank=True, help_text="e.g. MBChB, FRNZCGP", max_length=200)),
                ("bio", models.TextField(blank=True)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("phone", models.CharField(blank=True, max_length=20, validators=[PHONE_VALIDATOR])),
                ("room", models.CharField(blank=True, max_length=30, verbose_name="Consultation room")),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Inactive doctors are hidden from patients and cannot be booked.",
                    ),
                ),
            ],
            options={
                "ordering": ["last_name", "first_name"],
            },
        ),
        migrations.CreateModel(
            name="AppointmentSlot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("date", models.DateField()),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Untick to block this slot (e.g. doctor unavailable).",
                        verbose_name="Open for booking",
                    ),
                ),
                (
                    "doctor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="slots",
                        to="clinic.doctor",
                    ),
                ),
            ],
            options={
                "ordering": ["date", "start_time", "doctor__last_name"],
                "indexes": [models.Index(fields=["date", "start_time"], name="slot_date_time_idx")],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("doctor", "date", "start_time"),
                        name="unique_slot_per_doctor_time",
                        violation_error_message="This doctor already has a slot starting at that time.",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("end_time__gt", models.F("start_time"))),
                        name="slot_end_after_start",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Appointment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("reason", models.TextField(max_length=500, verbose_name="Reason for visit")),
                (
                    "status",
                    models.CharField(
                        choices=[("booked", "Booked"), ("cancelled", "Cancelled"), ("completed", "Completed")],
                        default="booked",
                        max_length=10,
                    ),
                ),
                ("admin_notes", models.TextField(blank=True, verbose_name="Staff notes")),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                (
                    "patient",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="appointments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "slot",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="appointments",
                        to="clinic.appointmentslot",
                    ),
                ),
            ],
            options={
                "ordering": ["slot__date", "slot__start_time"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status", "booked")),
                        fields=("slot",),
                        name="one_active_booking_per_slot",
                        violation_error_message="This time slot has already been booked.",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DoctorSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "weekday",
                    models.IntegerField(
                        choices=[
                            (0, "Monday"),
                            (1, "Tuesday"),
                            (2, "Wednesday"),
                            (3, "Thursday"),
                            (4, "Friday"),
                            (5, "Saturday"),
                            (6, "Sunday"),
                        ]
                    ),
                ),
                ("start_time", models.TimeField()),
                ("end_time", models.TimeField()),
                (
                    "slot_minutes",
                    models.PositiveSmallIntegerField(
                        default=15,
                        help_text="Used when generating appointment slots from this schedule.",
                        verbose_name="Appointment length (minutes)",
                    ),
                ),
                (
                    "doctor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedules",
                        to="clinic.doctor",
                    ),
                ),
            ],
            options={
                "ordering": ["weekday", "start_time"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("doctor", "weekday", "start_time"),
                        name="unique_schedule_start_per_doctor_day",
                        violation_error_message="This doctor already has a session starting then on that day.",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("end_time__gt", models.F("start_time"))),
                        name="schedule_end_after_start",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=120)),
                ("message", models.TextField()),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "appointment",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="notifications",
                        to="clinic.appointment",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
