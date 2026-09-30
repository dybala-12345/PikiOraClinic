# roles:
# admin = staff user, uses the dashboard
# patient = any other logged in user, books appointments
# all the role checks use the 2 functions below

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect


def is_clinic_admin(user):
    return user.is_authenticated and user.is_active and user.is_staff


def is_patient(user):
    return user.is_authenticated and user.is_active and not user.is_staff


# decorators for function views
def patient_required(view_func):
    # patients only - staff get sent to the dashboard

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if is_clinic_admin(request.user):
            messages.info(request, "Administrators manage appointments from the dashboard.")
            return redirect("dashboard:home")
        return view_func(request, *args, **kwargs)

    return wrapper


def admin_required(view_func):
    # admins only

    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_clinic_admin(request.user):
            raise PermissionDenied("Administrator access only.")
        return view_func(request, *args, **kwargs)

    return wrapper


# mixin for class based views
class AdminRequiredMixin(AccessMixin):
    # used on all the dashboard pages
    # not logged in -> login page, patient -> 403 error

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not is_clinic_admin(request.user):
            raise PermissionDenied("Administrator access only.")
        return super().dispatch(request, *args, **kwargs)
