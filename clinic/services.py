# booking logic is here so patients and admins follow the same rules
#
# double booking is stopped 3 ways:
# 1. only free slots are shown
# 2. the slot row is locked while saving (select_for_update) and checked again
# 3. the database has a unique constraint so a slot can't have 2 active bookings

import logging
from datetime import datetime, timedelta

from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Appointment, AppointmentSlot, Doctor, DoctorSchedule, Notification

logger = logging.getLogger(__name__)


class BookingError(Exception):
    # error for when a booking isn't allowed - the message is shown to the user
    pass


# notifications
def notify(user, title, message, appointment=None):
    # saves a notification and also emails the user
    Notification.objects.create(user=user, title=title, message=message, appointment=appointment)
    if user.email:
        try:
            send_mail(
                subject=f"Piki Ora Medical Centre - {title}",
                message=f"Kia ora {user.first_name or user.username},\n\n{message}\n\n"
                "Ngā mihi,\nPiki Ora Medical Centre",
                from_email=None,  # uses DEFAULT_FROM_EMAIL from settings
                recipient_list=[user.email],
                fail_silently=False,
            )
        except Exception:  # don't let an email error break the booking
            logger.exception("Could not send notification e-mail to %s", user.email)


def _appointment_summary(appointment):
    slot = appointment.slot
    return (
        f"{slot.doctor.full_name} on {slot.date:%A %d %B %Y} "
        f"at {slot.start_time:%H:%M}"
        + (f" (room {slot.doctor.room})" if slot.doctor.room else "")
    )


# checks used when booking and when changing
def _lock_slot(slot_id):
    try:
        return AppointmentSlot.objects.select_for_update().select_related("doctor").get(pk=slot_id)
    except AppointmentSlot.DoesNotExist:
        raise BookingError("That appointment slot no longer exists.") from None


def _check_slot_bookable(slot, patient, ignore_appointment=None):
    if not slot.is_active or not slot.doctor.is_active:
        raise BookingError("This slot is not open for booking.")
    if slot.is_past:
        raise BookingError("This slot is in the past. Please choose a future time.")

    taken = slot.appointments.filter(status=Appointment.Status.BOOKED)
    if ignore_appointment is not None:
        taken = taken.exclude(pk=ignore_appointment.pk)
    if taken.exists():
        raise BookingError("Sorry, this slot has just been booked by someone else. Please choose another time.")

    # a patient can't have 2 appointments at the same time
    clash = Appointment.objects.booked().filter(
        patient=patient,
        slot__date=slot.date,
        slot__start_time__lt=slot.end_time,
        slot__end_time__gt=slot.start_time,
    )
    if ignore_appointment is not None:
        clash = clash.exclude(pk=ignore_appointment.pk)
    if clash.exists():
        raise BookingError("You already have another appointment at this time.")


# main functions
def book_appointment(*, patient, slot_id, reason):
    # books a slot for a patient
    try:
        with transaction.atomic():
            slot = _lock_slot(slot_id)
            _check_slot_bookable(slot, patient)
            appointment = Appointment.objects.create(patient=patient, slot=slot, reason=reason)
    except IntegrityError:
        # someone else booked it at the same moment - the db constraint caught it
        raise BookingError("Sorry, this slot has just been booked by someone else. Please choose another time.") from None

    notify(
        patient,
        "Appointment confirmed",
        f"Your appointment with {_appointment_summary(appointment)} is confirmed. "
        f"Reason for visit: {reason}\n\n"
        "You can view, change or cancel it under 'My appointments' when you log in.",
        appointment,
    )
    return appointment


def change_appointment(appointment, *, new_slot_id, reason, changed_by_admin=False, status=None, admin_notes=None):
    # move an appointment or update it - used by patient edit and admin edit
    old_slot_id = appointment.slot_id
    try:
        with transaction.atomic():
            appointment = Appointment.objects.select_for_update().get(pk=appointment.pk)
            new_status = status or appointment.status

            if new_slot_id != old_slot_id or (
                new_status == Appointment.Status.BOOKED and appointment.status != Appointment.Status.BOOKED
            ):
                slot = _lock_slot(new_slot_id)
                _check_slot_bookable(slot, appointment.patient, ignore_appointment=appointment)
                appointment.slot = slot

            appointment.reason = reason
            appointment.status = new_status
            if admin_notes is not None:
                appointment.admin_notes = admin_notes
            if new_status == Appointment.Status.CANCELLED and appointment.cancelled_at is None:
                appointment.cancelled_at = timezone.now()
            elif new_status != Appointment.Status.CANCELLED:
                appointment.cancelled_at = None
            appointment.save()
    except IntegrityError:
        raise BookingError("Sorry, that slot has just been booked by someone else. Please choose another time.") from None

    who = "The clinic has updated" if changed_by_admin else "You updated"
    notify(
        appointment.patient,
        "Appointment updated",
        f"{who} your appointment. It is now: {_appointment_summary(appointment)} "
        f"(status: {appointment.get_status_display()}).",
        appointment,
    )
    return appointment


def cancel_appointment(appointment, *, cancelled_by_admin=False):
    # cancel it so the slot is free again
    if appointment.status != Appointment.Status.BOOKED:
        raise BookingError("Only booked appointments can be cancelled.")
    appointment.status = Appointment.Status.CANCELLED
    appointment.cancelled_at = timezone.now()
    appointment.save(update_fields=["status", "cancelled_at", "updated_at"])

    who = "The clinic has cancelled" if cancelled_by_admin else "You cancelled"
    notify(
        appointment.patient,
        "Appointment cancelled",
        f"{who} your appointment with {_appointment_summary(appointment)}.",
        appointment,
    )
    return appointment


def generate_slots(*, start_date, end_date, doctors=None):
    # makes slots from each doctor's weekly schedule between the 2 dates
    # skips slots that already exist so it's safe to run again
    if doctors is None:
        doctors = Doctor.objects.filter(is_active=True)
    schedules = list(DoctorSchedule.objects.filter(doctor__in=doctors).select_related("doctor"))

    existing = {}
    for slot in AppointmentSlot.objects.filter(doctor__in=doctors, date__range=(start_date, end_date)):
        existing.setdefault((slot.doctor_id, slot.date), []).append((slot.start_time, slot.end_time))

    new_slots = []
    day = start_date
    while day <= end_date:
        for schedule in schedules:
            if schedule.weekday != day.weekday():
                continue
            taken = existing.setdefault((schedule.doctor_id, day), [])
            current = datetime.combine(day, schedule.start_time)
            finish = datetime.combine(day, schedule.end_time)
            step = timedelta(minutes=schedule.slot_minutes)
            while current + step <= finish:
                start, end = current.time(), (current + step).time()
                overlaps = any(s < end and e > start for s, e in taken)
                if not overlaps:
                    new_slots.append(
                        AppointmentSlot(doctor=schedule.doctor, date=day, start_time=start, end_time=end)
                    )
                    taken.append((start, end))
                current += step
        day += timedelta(days=1)

    AppointmentSlot.objects.bulk_create(new_slots)
    return len(new_slots)


def default_generation_range(days=14):
    today = timezone.localdate()
    return today, today + timedelta(days=days - 1)
