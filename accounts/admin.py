# Django Admin registration - for development and testing only.
# Clinic staff manage patient accounts through the custom dashboard (/dashboard/patients/).
from django.contrib import admin

from .models import PatientProfile


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone", "date_of_birth")
    search_fields = ("user__username", "user__first_name", "user__last_name", "phone")
