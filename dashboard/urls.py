from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.DashboardHomeView.as_view(), name="home"),
    # Doctors and weekly schedules
    path("doctors/", views.DoctorListView.as_view(), name="doctor_list"),
    path("doctors/add/", views.DoctorCreateView.as_view(), name="doctor_add"),
    path("doctors/<int:pk>/", views.DoctorDetailView.as_view(), name="doctor_detail"),
    path("doctors/<int:pk>/edit/", views.DoctorUpdateView.as_view(), name="doctor_edit"),
    path("doctors/<int:pk>/delete/", views.DoctorDeleteView.as_view(), name="doctor_delete"),
    path("doctors/<int:doctor_pk>/schedule/add/", views.schedule_add, name="schedule_add"),
    path("schedule/<int:pk>/delete/", views.schedule_delete, name="schedule_delete"),
    # Appointment slots
    path("slots/", views.SlotListView.as_view(), name="slot_list"),
    path("slots/add/", views.SlotCreateView.as_view(), name="slot_add"),
    path("slots/generate/", views.slot_generate, name="slot_generate"),
    path("slots/<int:pk>/edit/", views.SlotUpdateView.as_view(), name="slot_edit"),
    path("slots/<int:pk>/delete/", views.SlotDeleteView.as_view(), name="slot_delete"),
    path("slots/<int:pk>/toggle/", views.slot_toggle, name="slot_toggle"),
    # Appointments
    path("appointments/", views.AppointmentListView.as_view(), name="appointment_list"),
    path("appointments/<int:pk>/edit/", views.appointment_edit, name="appointment_edit"),
    path("appointments/<int:pk>/cancel/", views.appointment_cancel, name="appointment_cancel"),
    # Patient accounts
    path("patients/", views.PatientListView.as_view(), name="patient_list"),
    path("patients/add/", views.patient_create, name="patient_add"),
    path("patients/<int:pk>/", views.PatientDetailView.as_view(), name="patient_detail"),
    path("patients/<int:pk>/edit/", views.patient_edit, name="patient_edit"),
    path("patients/<int:pk>/toggle-active/", views.patient_toggle_active, name="patient_toggle_active"),
    path("patients/<int:pk>/password/", views.patient_set_password, name="patient_set_password"),
    path("patients/<int:pk>/delete/", views.PatientDeleteView.as_view(), name="patient_delete"),
]
