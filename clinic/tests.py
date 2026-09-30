# tests - run with: python manage.py test

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import PatientProfile

from .models import Appointment, AppointmentSlot, Doctor, DoctorSchedule, Notification
from .services import BookingError, book_appointment, cancel_appointment, generate_slots

User = get_user_model()


class ClinicTestCase(TestCase):
    # test data for all the tests: 1 doctor, 2 slots, 2 patients, 1 admin

    @classmethod
    def setUpTestData(cls):
        cls.doctor = Doctor.objects.create(first_name="Aroha", last_name="Ngata")
        tomorrow = timezone.localdate() + timedelta(days=1)
        cls.slot = AppointmentSlot.objects.create(doctor=cls.doctor, date=tomorrow, start_time=time(9), end_time=time(9, 15))
        cls.slot2 = AppointmentSlot.objects.create(doctor=cls.doctor, date=tomorrow, start_time=time(9, 15), end_time=time(9, 30))
        cls.patient = User.objects.create_user("alice", "alice@example.com", "Str0ng-Pass!", first_name="Alice")
        cls.other = User.objects.create_user("bob", "bob@example.com", "Str0ng-Pass!", first_name="Bob")
        PatientProfile.objects.create(user=cls.patient)
        PatientProfile.objects.create(user=cls.other)
        cls.admin = User.objects.create_user("staff", "staff@example.com", "Str0ng-Pass!", is_staff=True)


class DoubleBookingTests(ClinicTestCase):
    def test_booking_creates_appointment_and_notification(self):
        appointment = book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="Check-up")
        self.assertEqual(appointment.status, Appointment.Status.BOOKED)
        self.assertTrue(Notification.objects.filter(user=self.patient, appointment=appointment).exists())

    def test_same_slot_cannot_be_booked_twice(self):
        book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="Check-up")
        with self.assertRaises(BookingError):
            book_appointment(patient=self.other, slot_id=self.slot.pk, reason="Flu")
        self.assertEqual(Appointment.objects.filter(slot=self.slot).count(), 1)

    def test_database_constraint_blocks_double_booking(self):
        Appointment.objects.create(patient=self.patient, slot=self.slot, reason="A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.create(patient=self.other, slot=self.slot, reason="B")

    def test_cancelled_slot_can_be_booked_again(self):
        appointment = book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="Check-up")
        cancel_appointment(appointment)
        again = book_appointment(patient=self.other, slot_id=self.slot.pk, reason="Flu")
        self.assertEqual(again.slot, self.slot)

    def test_past_slot_cannot_be_booked(self):
        yesterday = timezone.localdate() - timedelta(days=1)
        past = AppointmentSlot.objects.create(doctor=self.doctor, date=yesterday, start_time=time(9), end_time=time(9, 15))
        with self.assertRaises(BookingError):
            book_appointment(patient=self.patient, slot_id=past.pk, reason="Too late")

    def test_available_excludes_booked_slots(self):
        book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="Check-up")
        available = AppointmentSlot.objects.available()
        self.assertNotIn(self.slot, available)
        self.assertIn(self.slot2, available)


class PatientViewTests(ClinicTestCase):
    def test_booking_requires_login(self):
        response = self.client.get(reverse("clinic:book", args=[self.slot.pk]))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('clinic:book', args=[self.slot.pk])}")

    def test_patient_can_book_through_the_website(self):
        self.client.force_login(self.patient)
        response = self.client.post(reverse("clinic:book", args=[self.slot.pk]), {"reason": "Sore throat"})
        appointment = Appointment.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse("clinic:booking_confirmed", args=[appointment.pk]))

    def test_patient_cannot_see_someone_elses_appointment(self):
        appointment = book_appointment(patient=self.other, slot_id=self.slot.pk, reason="Private")
        self.client.force_login(self.patient)
        response = self.client.get(reverse("clinic:appointment_detail", args=[appointment.pk]))
        self.assertEqual(response.status_code, 404)

    def test_patient_can_move_appointment_to_free_slot(self):
        appointment = book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="Check-up")
        self.client.force_login(self.patient)
        self.client.post(
            reverse("clinic:appointment_edit", args=[appointment.pk]),
            {"slot": self.slot2.pk, "reason": "Check-up (moved)"},
        )
        appointment.refresh_from_db()
        self.assertEqual(appointment.slot, self.slot2)

    def test_patient_can_cancel(self):
        appointment = book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="Check-up")
        self.client.force_login(self.patient)
        self.client.post(reverse("clinic:appointment_cancel", args=[appointment.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)

    def test_registration_creates_patient_profile(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "newpatient",
                "first_name": "New",
                "last_name": "Patient",
                "email": "new@example.com",
                "phone": "021 123 4567",
                "date_of_birth": "1990-05-01",
                "password1": "Very-Secure-123",
                "password2": "Very-Secure-123",
            },
        )
        self.assertRedirects(response, reverse("clinic:doctor_list"))
        user = User.objects.get(username="newpatient")
        self.assertFalse(user.is_staff)
        self.assertTrue(PatientProfile.objects.filter(user=user).exists())


class SlotGenerationTests(TestCase):
    def test_generate_slots_from_schedule_and_skip_existing(self):
        doctor = Doctor.objects.create(first_name="James", last_name="Chen")
        start = timezone.localdate() + timedelta(days=1)
        DoctorSchedule.objects.create(doctor=doctor, weekday=start.weekday(), start_time=time(9), end_time=time(10), slot_minutes=15)
        self.assertEqual(generate_slots(start_date=start, end_date=start), 4)
        self.assertEqual(generate_slots(start_date=start, end_date=start), 0)  # running it again shouldn't make duplicates


class DashboardAccessTests(ClinicTestCase):
    def test_dashboard_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_patients_are_forbidden_from_dashboard(self):
        self.client.force_login(self.patient)
        for name in ("dashboard:home", "dashboard:doctor_list", "dashboard:appointment_list", "dashboard:patient_list"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_admin_pages_load(self):
        book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="Check-up")
        self.client.force_login(self.admin)
        pages = [
            reverse("dashboard:home"),
            reverse("dashboard:doctor_list"),
            reverse("dashboard:doctor_detail", args=[self.doctor.pk]),
            reverse("dashboard:doctor_add"),
            reverse("dashboard:slot_list"),
            reverse("dashboard:slot_add"),
            reverse("dashboard:slot_generate"),
            reverse("dashboard:appointment_list"),
            reverse("dashboard:patient_list"),
            reverse("dashboard:patient_detail", args=[self.patient.pk]),
            reverse("dashboard:patient_edit", args=[self.patient.pk]),
            reverse("dashboard:patient_add"),
        ]
        for url in pages:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_admin_can_add_doctor(self):
        self.client.force_login(self.admin)
        self.client.post(
            reverse("dashboard:doctor_add"),
            {"first_name": "Priya", "last_name": "Sharma", "specialisation": "Paediatrics", "is_active": "on"},
        )
        self.assertTrue(Doctor.objects.filter(last_name="Sharma").exists())

    def test_admin_can_cancel_any_appointment(self):
        appointment = book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="Check-up")
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:appointment_cancel", args=[appointment.pk]))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.CANCELLED)

    def test_admin_cannot_move_appointment_onto_booked_slot(self):
        first = book_appointment(patient=self.patient, slot_id=self.slot.pk, reason="A")
        book_appointment(patient=self.other, slot_id=self.slot2.pk, reason="B")
        self.client.force_login(self.admin)
        self.client.post(
            reverse("dashboard:appointment_edit", args=[first.pk]),
            {"slot": self.slot2.pk, "status": "booked", "reason": "A", "admin_notes": ""},
        )
        first.refresh_from_db()
        self.assertEqual(first.slot, self.slot)

    def test_admin_can_deactivate_patient(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("dashboard:patient_toggle_active", args=[self.patient.pk]))
        self.patient.refresh_from_db()
        self.assertFalse(self.patient.is_active)
