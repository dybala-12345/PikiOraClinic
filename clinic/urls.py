from django.urls import path

from . import views

app_name = "clinic"

urlpatterns = [
    path("", views.home, name="home"),
    path("doctors/", views.doctor_list, name="doctor_list"),
    path("doctors/<int:pk>/", views.doctor_detail, name="doctor_detail"),
    path("book/<int:slot_id>/", views.book, name="book"),
    path("appointments/", views.my_appointments, name="my_appointments"),
    path("appointments/<int:pk>/", views.appointment_detail, name="appointment_detail"),
    path("appointments/<int:pk>/confirmed/", views.booking_confirmed, name="booking_confirmed"),
    path("appointments/<int:pk>/edit/", views.appointment_edit, name="appointment_edit"),
    path("appointments/<int:pk>/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("notifications/", views.notifications, name="notifications"),
    path("notifications/read/", views.notifications_mark_read, name="notifications_mark_read"),
]
