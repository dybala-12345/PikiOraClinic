from datetime import timedelta
from itertools import groupby

from django.contrib import messages
from django.db.models import OuterRef, Prefetch, Q, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.permissions import is_clinic_admin, patient_required

from .forms import AppointmentEditForm, BookingForm, DoctorFilterForm
from .models import Appointment, AppointmentSlot, Doctor, DoctorSchedule, Notification
from .services import BookingError, book_appointment, cancel_appointment, change_appointment

BOOKING_WINDOW_DAYS = 30  # patients can see slots up to 30 days ahead


def _doctors_with_next_slot(queryset):
    # adds the next free slot date/time to each doctor
    next_slot = AppointmentSlot.objects.filter(doctor=OuterRef("pk")).available().order_by("date", "start_time")
    return queryset.annotate(
        next_slot_date=Subquery(next_slot.values("date")[:1]),
        next_slot_time=Subquery(next_slot.values("start_time")[:1]),
    ).prefetch_related(Prefetch("schedules", queryset=DoctorSchedule.objects.order_by("weekday", "start_time")))


def home(request):
    doctors = _doctors_with_next_slot(Doctor.objects.filter(is_active=True))[:3]
    context = {
        "doctors": doctors,
        "doctor_count": Doctor.objects.filter(is_active=True).count(),
        "available_count": AppointmentSlot.objects.available().count(),
    }
    if request.user.is_authenticated and not is_clinic_admin(request.user):
        context["next_appointment"] = (
            Appointment.objects.booked().upcoming().filter(patient=request.user).select_related("slot__doctor").first()
        )
    return render(request, "clinic/home.html", context)


def doctor_list(request):
    # list of doctors + their weekly hours
    form = DoctorFilterForm(request.GET or None)
    doctors = Doctor.objects.filter(is_active=True)
    if form.is_valid():
        query = form.cleaned_data.get("q")
        specialisation = form.cleaned_data.get("specialisation")
        if query:
            doctors = doctors.filter(
                Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(specialisation__icontains=query)
            )
        if specialisation:
            doctors = doctors.filter(specialisation=specialisation)
    return render(
        request,
        "clinic/doctor_list.html",
        {"doctors": _doctors_with_next_slot(doctors), "form": form},
    )


def doctor_detail(request, pk):
    # doctor page with free slots grouped by day
    doctors = Doctor.objects.all() if is_clinic_admin(request.user) else Doctor.objects.filter(is_active=True)
    doctor = get_object_or_404(doctors, pk=pk)

    today = timezone.localdate()
    slots = (
        AppointmentSlot.objects.filter(doctor=doctor, date__lte=today + timedelta(days=BOOKING_WINDOW_DAYS))
        .available()
        .order_by("date", "start_time")
    )
    slots_by_day = [(day, list(day_slots)) for day, day_slots in groupby(slots, key=lambda s: s.date)]

    return render(
        request,
        "clinic/doctor_detail.html",
        {
            "doctor": doctor,
            "schedules": doctor.schedules.all(),
            "slots_by_day": slots_by_day,
            "booking_window_days": BOOKING_WINDOW_DAYS,
        },
    )


# booking pages (patients only, must be logged in)
@patient_required
def book(request, slot_id):
    slot = get_object_or_404(AppointmentSlot.objects.select_related("doctor"), pk=slot_id)

    if not AppointmentSlot.objects.available().filter(pk=slot.pk).exists():
        messages.error(request, "Sorry, that slot is no longer available. Please choose another time.")
        return redirect(slot.doctor.get_absolute_url())

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            try:
                appointment = book_appointment(
                    patient=request.user, slot_id=slot.pk, reason=form.cleaned_data["reason"]
                )
            except BookingError as error:
                messages.error(request, str(error))
                return redirect(slot.doctor.get_absolute_url())
            return redirect("clinic:booking_confirmed", pk=appointment.pk)
    else:
        form = BookingForm()

    return render(request, "clinic/book.html", {"slot": slot, "form": form})


@patient_required
def booking_confirmed(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related("slot__doctor"), pk=pk, patient=request.user
    )
    return render(request, "clinic/booking_confirmed.html", {"appointment": appointment})


@patient_required
def my_appointments(request):
    mine = Appointment.objects.filter(patient=request.user).select_related("slot__doctor")
    upcoming = mine.booked().upcoming()
    history = mine.exclude(pk__in=upcoming.values("pk")).order_by("-slot__date", "-slot__start_time")
    return render(request, "clinic/my_appointments.html", {"upcoming": upcoming, "history": history})


@patient_required
def appointment_detail(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related("slot__doctor"), pk=pk, patient=request.user
    )
    return render(request, "clinic/appointment_detail.html", {"appointment": appointment})


@patient_required
def appointment_edit(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related("slot__doctor"), pk=pk, patient=request.user
    )
    if not appointment.can_be_changed:
        messages.error(request, "Only upcoming, booked appointments can be changed.")
        return redirect(appointment.get_absolute_url())

    if request.method == "POST":
        form = AppointmentEditForm(request.POST, appointment=appointment)
        if form.is_valid():
            try:
                change_appointment(
                    appointment,
                    new_slot_id=form.cleaned_data["slot"].pk,
                    reason=form.cleaned_data["reason"],
                )
            except BookingError as error:
                form.add_error("slot", str(error))
            else:
                messages.success(request, "Your appointment has been updated.")
                return redirect(appointment.get_absolute_url())
    else:
        form = AppointmentEditForm(appointment=appointment)

    return render(request, "clinic/appointment_edit.html", {"appointment": appointment, "form": form})


@patient_required
def appointment_cancel(request, pk):
    appointment = get_object_or_404(
        Appointment.objects.select_related("slot__doctor"), pk=pk, patient=request.user
    )
    if not appointment.can_be_changed:
        messages.error(request, "Only upcoming, booked appointments can be cancelled.")
        return redirect(appointment.get_absolute_url())

    if request.method == "POST":
        try:
            cancel_appointment(appointment)
        except BookingError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Your appointment has been cancelled.")
        return redirect("clinic:my_appointments")

    return render(request, "clinic/appointment_cancel.html", {"appointment": appointment})


# notifications
@patient_required
def notifications(request):
    items = list(Notification.objects.filter(user=request.user).select_related("appointment")[:50])
    return render(request, "clinic/notifications.html", {"notifications": items})


@require_POST
@patient_required
def notifications_mark_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("clinic:notifications")
