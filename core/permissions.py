"""
Role-based access control.

The system has two roles:

* Administrator - a staff user (``is_staff=True``). Uses the custom dashboard.
* Patient       - any other active, logged-in user. Books appointments.

All role checks go through the two helper functions below so the rule is
defined in exactly one place.
"""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def is_clinic_admin(user):
    """True for authorised clinic staff."""
    return user.is_authenticated and user.is_active and user.is_staff


def is_patient(user):
    """True for logged-in patients (non-staff users)."""
    return user.is_authenticated and user.is_active and not user.is_staff


# ---------------------------------------------------------------------------
# Function-based view decorators
# ---------------------------------------------------------------------------
def patient_required(view_func):
    """Only logged-in patients may use the view; staff go to the dashboard."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if is_clinic_admin(request.user):
            messages.info(request, "Administrators manage appointments from the dashboard.")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_required(view_func):
    """Only clinic administrators may use the view."""

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_clinic_admin(request.user):
            raise PermissionDenied("Administrator access only.")
        return view_func(request, *args, **kwargs)

    return wrapper


# ---------------------------------------------------------------------------
# Class-based view mixin
# ---------------------------------------------------------------------------
class AdminRequiredMixin(AccessMixin):
    """
    Protects every custom dashboard view.

    Anonymous users are sent to the login page; logged-in non-staff users get
    a 403 Forbidden page.
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_clinic_admin(request.user):
            raise PermissionDenied("Administrator access only.")
        return super().dispatch(request, *args, **kwargs)
