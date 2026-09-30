# adds demo doctors, schedules, slots and 2 test users
# run: python manage.py seed_demo  (add --if-empty to only run when there are no doctors yet)

from datetime import time, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import PatientProfile
from clinic.models import Appointment, AppointmentSlot, Doctor, DoctorSchedule
from clinic.services import BookingError, book_appointment, generate_slots

DOCTORS = [
    {
        "first_name": "Aroha",
        "last_name": "Ngata",
        "specialisation": "General Practitioner",
        "qualifications": "MBChB, FRNZCGP",
        "room": "1",
        "bio": "Aroha has over 12 years of experience in whānau-centred general practice.",
        "sessions": [(0, 9, 12), (0, 13, 17), (2, 9, 12), (4, 9, 13)],
    },
    {
        "first_name": "James",
        "last_name": "Chen",
        "specialisation": "General Practitioner",
        "qualifications": "MBChB, DipObs",
        "room": "2",
        "bio": "James has a special interest in sports injuries and men's health.",
        "sessions": [(1, 8, 12), (3, 13, 17), (4, 13, 17)],
    },
    {
        "first_name": "Priya",
        "last_name": "Sharma",
        "specialisation": "Paediatrics",
        "qualifications": "MBBS, FRACP",
        "room": "3",
        "bio": "Priya looks after tamariki from newborns to teenagers.",
        "sessions": [(0, 13, 16), (2, 13, 17), (3, 9, 12)],
    },
    {
        "first_name": "Sione",
        "last_name": "Taufa",
        "specialisation": "Women's Health",
        "qualifications": "MBChB, DRANZCOG",
        "room": "4",
        "bio": "Sione provides cervical screening, contraception and antenatal care.",
        "sessions": [(1, 13, 17), (3, 9, 12), (5, 9, 12)],
    },
]


class Command(BaseCommand):
    help = "Load demonstration doctors, schedules, slots and demo user accounts."

    def add_arguments(self, parser):
        parser.add_argument("--if-empty", action="store_true", help="Only seed when there are no doctors yet.")
        parser.add_argument("--days", type=int, default=14, help="Number of days of slots to generate.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["if_empty"] and Doctor.objects.exists():
            self.stdout.write("Doctors already exist - demo data not loaded.")
            return

        for data in DOCTORS:
            sessions = data.pop("sessions")
            doctor, _ = Doctor.objects.get_or_create(
                first_name=data["first_name"], last_name=data["last_name"], defaults=data
            )
            data["sessions"] = sessions  # put it back so it still works if we run the command again
            for weekday, start_hour, end_hour in sessions:
                DoctorSchedule.objects.get_or_create(
                    doctor=doctor,
                    weekday=weekday,
                    start_time=time(start_hour),
                    defaults={"end_time": time(end_hour), "slot_minutes": 15},
                )

        today = timezone.localdate()
        created = generate_slots(start_date=today, end_date=today + timedelta(days=options["days"] - 1))
        self.stdout.write(f"Created {created} appointment slots.")

        User = get_user_model()
        admin, admin_created = User.objects.get_or_create(
            username="clinicadmin",
            defaults={"first_name": "Clinic", "last_name": "Admin", "email": "admin@pikiora.test", "is_staff": True},
        )
        if admin_created:
            admin.set_password("PikiOra@Admin2026")
            admin.save()

        patient, patient_created = User.objects.get_or_create(
            username="demopatient",
            defaults={"first_name": "Mere", "last_name": "Wilson", "email": "patient@pikiora.test"},
        )
        if patient_created:
            patient.set_password("PikiOra@Patient2026")
            patient.save()
            PatientProfile.objects.get_or_create(user=patient, defaults={"phone": "021 555 0101"})

        if not Appointment.objects.filter(patient=patient).exists():
            slot = AppointmentSlot.objects.available().order_by("date", "start_time").first()
            if slot:
                try:
                    book_appointment(patient=patient, slot_id=slot.pk, reason="Annual check-up")
                except BookingError:
                    pass

        self.stdout.write(self.style.SUCCESS("Demo data ready."))
        self.stdout.write("  Administrator: clinicadmin / PikiOra@Admin2026")
        self.stdout.write("  Patient:       demopatient / PikiOra@Patient2026")
