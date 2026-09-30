# django admin - only for testing, staff use /dashboard/ instead
from django.contrib import admin

from .models import Appointment, AppointmentSlot, Doctor, DoctorSchedule, Notification


class DoctorScheduleInline(admin.TabularInline):
    model = DoctorSchedule
    extra = 0


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ("full_name", "specialisation", "room", "is_active")
    list_filter = ("is_active", "specialisation")
    search_fields = ("first_name", "last_name", "specialisation")
    inlines = [DoctorScheduleInline]


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ("doctor", "weekday", "start_time", "end_time", "slot_minutes")
    list_filter = ("weekday", "doctor")


@admin.register(AppointmentSlot)
class AppointmentSlotAdmin(admin.ModelAdmin):
    list_display = ("doctor", "date", "start_time", "end_time", "is_active")
    list_filter = ("is_active", "doctor", "date")
    date_hierarchy = "date"


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "slot", "status", "created_at")
    list_filter = ("status", "slot__doctor")
    search_fields = ("patient__username", "patient__first_name", "patient__last_name", "reason")
    list_select_related = ("patient", "slot__doctor")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "is_read", "created_at")
    list_filter = ("is_read",)
