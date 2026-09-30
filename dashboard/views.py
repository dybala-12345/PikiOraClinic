# custom admin dashboard - every view here is admin only (AdminRequiredMixin / admin_required)
# we don't use the built in django admin for this

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, DetailView, ListView, TemplateView, UpdateView

from accounts.forms import PatientProfileForm
from accounts.models import PatientProfile
from clinic.models import Appointment, AppointmentSlot, Doctor, DoctorSchedule
from clinic.services import BookingError, cancel_appointment, change_appointment, generate_slots
from core.permissions import AdminRequiredMixin, admin_required

from .forms import (
    AdminAppointmentForm,
    AdminPatientCreateForm,
    AdminSetPasswordForm,
    AdminUserAccountForm,
    AppointmentFilterForm,
    DoctorForm,
    DoctorScheduleForm,
    GenerateSlotsForm,
    SlotFilterForm,
    SlotForm,
)

User = get_user_model()
PAGE_SIZE = 20


def patients_queryset():
    # only patient accounts, never staff
    return User.objects.filter(is_staff=False, is_superuser=False)


# overview
class DashboardHomeView(AdminRequiredMixin, TemplateView):
    template_name = "dashboard/home.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        booked = Appointment.objects.booked().select_related("patient", "slot__doctor")
        context.update(
            {
                "stats": {
                    "doctors": Doctor.objects.filter(is_active=True).count(),
                    "patients": patients_queryset().count(),
                    "today": booked.filter(slot__date=today).count(),
                    "upcoming": booked.upcoming().count(),
                    "free_week": AppointmentSlot.objects.available()
                    .filter(date__lte=today + timedelta(days=7))
                    .count(),
                },
                "todays_appointments": booked.filter(slot__date=today).order_by("slot__start_time"),
                "recent_bookings": Appointment.objects.select_related("patient", "slot__doctor").order_by("-created_at")[:6],
            }
        )
        return context


# doctors
class DoctorListView(AdminRequiredMixin, ListView):
    template_name = "dashboard/doctor_list.html"
    context_object_name = "doctors"

    def get_queryset(self):
        now = timezone.localtime()
        upcoming = Q(slots__appointments__status=Appointment.Status.BOOKED) & (
            Q(slots__date__gt=now.date()) | Q(slots__date=now.date(), slots__start_time__gt=now.time())
        )
        return Doctor.objects.annotate(
            upcoming_count=Count("slots__appointments", filter=upcoming, distinct=True),
            schedule_count=Count("schedules", distinct=True),
        ).order_by("-is_active", "last_name")


class DoctorCreateView(AdminRequiredMixin, CreateView):
    model = Doctor
    form_class = DoctorForm
    template_name = "dashboard/form.html"
    extra_context = {"title": "Add doctor", "back_url": reverse_lazy("dashboard:doctor_list")}

    def form_valid(self, form):
        messages.success(self.request, f"{form.instance.full_name} added. Now add their weekly schedule.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("dashboard:doctor_detail", args=[self.object.pk])


class DoctorUpdateView(AdminRequiredMixin, UpdateView):
    model = Doctor
    form_class = DoctorForm
    template_name = "dashboard/form.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Edit {self.object.full_name}"
        context["back_url"] = reverse("dashboard:doctor_detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        messages.success(self.request, "Doctor profile updated.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("dashboard:doctor_detail", args=[self.object.pk])


class DoctorDetailView(AdminRequiredMixin, DetailView):
    model = Doctor
    template_name = "dashboard/doctor_detail.html"
    context_object_name = "doctor"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["schedules"] = self.object.schedules.all()
        context["schedule_form"] = kwargs.get("schedule_form") or DoctorScheduleForm()
        context["upcoming_appointments"] = (
            Appointment.objects.booked().upcoming().filter(slot__doctor=self.object).select_related("patient", "slot")[:10]
        )
        context["free_slot_count"] = AppointmentSlot.objects.filter(doctor=self.object).available().count()
        return context


class DoctorDeleteView(AdminRequiredMixin, DeleteView):
    model = Doctor
    template_name = "dashboard/confirm_delete.html"
    success_url = reverse_lazy("dashboard:doctor_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Delete {self.object.full_name}?"
        context["warning"] = (
            "This removes the doctor, their schedule and all of their empty slots. "
            "Doctors with appointment history cannot be deleted - mark them inactive instead."
        )
        context["back_url"] = reverse("dashboard:doctor_detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                response = super().form_valid(form)
        except ProtectedError:
            messages.error(
                self.request,
                "This doctor has appointment history and cannot be deleted. "
                "Edit the profile and untick 'Is active' instead.",
            )
            return redirect("dashboard:doctor_detail", pk=self.object.pk)
        messages.success(self.request, "Doctor deleted.")
        return response


@require_POST
@admin_required
def schedule_add(request, doctor_pk):
    doctor = get_object_or_404(Doctor, pk=doctor_pk)
    form = DoctorScheduleForm(request.POST, doctor=doctor)
    if form.is_valid():
        form.save()
        messages.success(request, "Consultation session added.")
        return redirect("dashboard:doctor_detail", pk=doctor.pk)
    view = DoctorDetailView()
    view.setup(request, pk=doctor.pk)
    view.object = doctor
    context = view.get_context_data(schedule_form=form)
    messages.error(request, "Please fix the errors in the schedule form.")
    return render(request, DoctorDetailView.template_name, context)


@require_POST
@admin_required
def schedule_delete(request, pk):
    schedule = get_object_or_404(DoctorSchedule, pk=pk)
    doctor_pk = schedule.doctor_id
    schedule.delete()
    messages.success(request, "Consultation session removed. Existing slots were not changed.")
    return redirect("dashboard:doctor_detail", pk=doctor_pk)


# slots
class SlotListView(AdminRequiredMixin, ListView):
    template_name = "dashboard/slot_list.html"
    context_object_name = "slots"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        self.filter_form = SlotFilterForm(self.request.GET or None)
        slots = AppointmentSlot.objects.select_related("doctor").with_booking_status()
        data = self.filter_form.cleaned_data if self.filter_form.is_valid() else {}

        if not data.get("show_past"):
            slots = slots.upcoming()
        if data.get("doctor"):
            slots = slots.filter(doctor=data["doctor"])
        if data.get("date"):
            slots = slots.filter(date=data["date"])
        status = data.get("status")
        if status == "available":
            slots = slots.filter(is_active=True, has_booking=False)
        elif status == "booked":
            slots = slots.filter(has_booking=True)
        elif status == "closed":
            slots = slots.filter(is_active=False)
        return slots.order_by("date", "start_time", "doctor__last_name")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        return context


class SlotCreateView(AdminRequiredMixin, CreateView):
    model = AppointmentSlot
    form_class = SlotForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:slot_list")
    extra_context = {"title": "Add appointment slot", "back_url": reverse_lazy("dashboard:slot_list")}

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("doctor"):
            initial["doctor"] = self.request.GET["doctor"]
        return initial

    def form_valid(self, form):
        messages.success(self.request, "Appointment slot created.")
        return super().form_valid(form)


class SlotUpdateView(AdminRequiredMixin, UpdateView):
    model = AppointmentSlot
    form_class = SlotForm
    template_name = "dashboard/form.html"
    success_url = reverse_lazy("dashboard:slot_list")
    extra_context = {"title": "Edit appointment slot", "back_url": reverse_lazy("dashboard:slot_list")}

    def form_valid(self, form):
        if self.object.is_booked and form.has_changed() and set(form.changed_data) - {"is_active"}:
            form.add_error(
                None,
                "This slot has an active booking. Move or cancel the appointment before changing its time or doctor.",
            )
            return self.form_invalid(form)
        messages.success(self.request, "Appointment slot updated.")
        return super().form_valid(form)


class SlotDeleteView(AdminRequiredMixin, DeleteView):
    model = AppointmentSlot
    template_name = "dashboard/confirm_delete.html"
    success_url = reverse_lazy("dashboard:slot_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Delete slot {self.object}?"
        context["warning"] = "Slots that have any appointment history cannot be deleted - close them instead."
        context["back_url"] = reverse("dashboard:slot_list")
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                response = super().form_valid(form)
        except ProtectedError:
            messages.error(self.request, "This slot has appointment history, so it was closed instead of deleted.")
            AppointmentSlot.objects.filter(pk=self.object.pk).update(is_active=False)
            return redirect("dashboard:slot_list")
        messages.success(self.request, "Appointment slot deleted.")
        return response


@require_POST
@admin_required
def slot_toggle(request, pk):
    slot = get_object_or_404(AppointmentSlot, pk=pk)
    slot.is_active = not slot.is_active
    slot.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"Slot {'opened' if slot.is_active else 'closed'} for booking.")
    next_url = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return redirect(next_url)
    return redirect("dashboard:slot_list")


@admin_required
def slot_generate(request):
    # create lots of slots at once from the weekly schedules
    form = GenerateSlotsForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        doctor = form.cleaned_data["doctor"]
        created = generate_slots(
            start_date=form.cleaned_data["start_date"],
            end_date=form.cleaned_data["end_date"],
            doctors=Doctor.objects.filter(pk=doctor.pk) if doctor else None,
        )
        if created:
            messages.success(request, f"{created} new appointment slot(s) created.")
        else:
            messages.warning(
                request,
                "No new slots were created. Check that the doctor has a weekly schedule "
                "for those days, or the slots may already exist.",
            )
        return redirect("dashboard:slot_list")
    return render(request, "dashboard/slot_generate.html", {"form": form})


# appointments
class AppointmentListView(AdminRequiredMixin, ListView):
    template_name = "dashboard/appointment_list.html"
    context_object_name = "appointments"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        self.filter_form = AppointmentFilterForm(self.request.GET or None)
        appointments = Appointment.objects.select_related("patient", "slot__doctor")
        data = self.filter_form.cleaned_data if self.filter_form.is_valid() else {}

        if data.get("q"):
            q = data["q"]
            appointments = appointments.filter(
                Q(patient__first_name__icontains=q)
                | Q(patient__last_name__icontains=q)
                | Q(patient__username__icontains=q)
                | Q(patient__email__icontains=q)
            )
        if data.get("doctor"):
            appointments = appointments.filter(slot__doctor=data["doctor"])
        if data.get("status"):
            appointments = appointments.filter(status=data["status"])
        if data.get("date_from"):
            appointments = appointments.filter(slot__date__gte=data["date_from"])
        if data.get("date_to"):
            appointments = appointments.filter(slot__date__lte=data["date_to"])
        return appointments.order_by("-slot__date", "-slot__start_time")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filter_form"] = self.filter_form
        return context


@admin_required
def appointment_edit(request, pk):
    appointment = get_object_or_404(Appointment.objects.select_related("patient", "slot__doctor"), pk=pk)
    form = AdminAppointmentForm(request.POST or None, appointment=appointment)
    if request.method == "POST" and form.is_valid():
        try:
            change_appointment(
                appointment,
                new_slot_id=form.cleaned_data["slot"].pk,
                reason=form.cleaned_data["reason"],
                status=form.cleaned_data["status"],
                admin_notes=form.cleaned_data["admin_notes"],
                changed_by_admin=True,
            )
        except BookingError as error:
            form.add_error("slot", str(error))
        else:
            messages.success(request, "Appointment updated and the patient has been notified.")
            return redirect("dashboard:appointment_list")
    return render(request, "dashboard/appointment_edit.html", {"appointment": appointment, "form": form})


@admin_required
def appointment_cancel(request, pk):
    appointment = get_object_or_404(Appointment.objects.select_related("patient", "slot__doctor"), pk=pk)
    if request.method == "POST":
        try:
            cancel_appointment(appointment, cancelled_by_admin=True)
        except BookingError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Appointment cancelled and the patient has been notified.")
        return redirect("dashboard:appointment_list")
    return render(request, "dashboard/appointment_cancel.html", {"appointment": appointment})


# patients
class PatientListView(AdminRequiredMixin, ListView):
    template_name = "dashboard/patient_list.html"
    context_object_name = "patients"
    paginate_by = PAGE_SIZE

    def get_queryset(self):
        patients = patients_queryset().select_related("patient_profile").annotate(
            appointment_count=Count("appointments", distinct=True),
            active_count=Count(
                "appointments",
                filter=Q(appointments__status=Appointment.Status.BOOKED),
                distinct=True,
            ),
        )
        self.query = self.request.GET.get("q", "").strip()
        if self.query:
            patients = patients.filter(
                Q(first_name__icontains=self.query)
                | Q(last_name__icontains=self.query)
                | Q(username__icontains=self.query)
                | Q(email__icontains=self.query)
                | Q(patient_profile__phone__icontains=self.query)
            )
        return patients.order_by("last_name", "first_name", "username")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["query"] = self.query
        return context


class PatientDetailView(AdminRequiredMixin, DetailView):
    template_name = "dashboard/patient_detail.html"
    context_object_name = "patient"

    def get_queryset(self):
        return patients_queryset().select_related("patient_profile")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["profile"] = PatientProfile.objects.filter(user=self.object).first()
        context["appointments"] = (
            self.object.appointments.select_related("slot__doctor").order_by("-slot__date", "-slot__start_time")
        )
        return context


@admin_required
def patient_create(request):
    form = AdminPatientCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Patient account '{user.username}' created.")
        return redirect("dashboard:patient_detail", pk=user.pk)
    return render(
        request,
        "dashboard/form.html",
        {"form": form, "title": "Add patient", "back_url": reverse("dashboard:patient_list")},
    )


@admin_required
def patient_edit(request, pk):
    patient = get_object_or_404(patients_queryset(), pk=pk)
    profile, _ = PatientProfile.objects.get_or_create(user=patient)
    user_form = AdminUserAccountForm(request.POST or None, instance=patient)
    profile_form = PatientProfileForm(request.POST or None, instance=profile)
    if request.method == "POST" and user_form.is_valid() and profile_form.is_valid():
        with transaction.atomic():
            user_form.save()
            profile_form.save()
        messages.success(request, "Patient account updated.")
        return redirect("dashboard:patient_detail", pk=patient.pk)
    return render(
        request,
        "dashboard/patient_edit.html",
        {"patient": patient, "user_form": user_form, "profile_form": profile_form},
    )


@require_POST
@admin_required
def patient_toggle_active(request, pk):
    patient = get_object_or_404(patients_queryset(), pk=pk)
    patient.is_active = not patient.is_active
    patient.save(update_fields=["is_active"])
    state = "activated" if patient.is_active else "deactivated - they can no longer log in"
    messages.success(request, f"Account {state}.")
    return redirect("dashboard:patient_detail", pk=patient.pk)


@admin_required
def patient_set_password(request, pk):
    patient = get_object_or_404(patients_queryset(), pk=pk)
    form = AdminSetPasswordForm(patient, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"New password set for {patient.username}.")
        return redirect("dashboard:patient_detail", pk=patient.pk)
    return render(
        request,
        "dashboard/form.html",
        {
            "form": form,
            "title": f"Set a new password for {patient.get_full_name() or patient.username}",
            "back_url": reverse("dashboard:patient_detail", args=[patient.pk]),
        },
    )


class PatientDeleteView(AdminRequiredMixin, DeleteView):
    template_name = "dashboard/confirm_delete.html"
    success_url = reverse_lazy("dashboard:patient_list")
    # can't be called 'user' or it replaces the logged in admin in the templates
    context_object_name = "patient"

    def get_queryset(self):
        return patients_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = f"Delete patient {self.object.get_full_name() or self.object.username}?"
        context["warning"] = (
            "This permanently deletes the account and all of its appointments. "
            "To keep the history, deactivate the account instead."
        )
        context["back_url"] = reverse("dashboard:patient_detail", args=[self.object.pk])
        return context

    def form_valid(self, form):
        messages.success(self.request, "Patient account deleted.")
        return super().form_valid(form)
