from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from core.permissions import is_clinic_admin, patient_required

from .forms import PatientProfileForm, PatientRegistrationForm, UserDetailsForm
from .models import PatientProfile


def register(request):
    # patient sign up page - logs them in straight after
    if request.user.is_authenticated:
        return redirect("accounts:after_login")

    if request.method == "POST":
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(
                request,
                f"Welcome, {user.first_name}! Your account has been created. "
                "Choose a doctor below to book your first appointment.",
            )
            return redirect("clinic:doctor_list")
    else:
        form = PatientRegistrationForm()
    return render(request, "accounts/register.html", {"form": form})


@login_required
def after_login(request):
    # admins go to the dashboard, patients go to their appointments
    if is_clinic_admin(request.user):
        return redirect("dashboard:home")
    return redirect("clinic:my_appointments")


@patient_required
def profile(request):
    # patients can edit their own details here
    patient_profile, _ = PatientProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        user_form = UserDetailsForm(request.POST, instance=request.user)
        profile_form = PatientProfileForm(request.POST, instance=patient_profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, "Your details have been updated.")
            return redirect("accounts:profile")
    else:
        user_form = UserDetailsForm(instance=request.user)
        profile_form = PatientProfileForm(instance=patient_profile)

    return render(
        request,
        "accounts/profile.html",
        {"user_form": user_form, "profile_form": profile_form},
    )
