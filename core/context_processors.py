"""Values made available to every template."""

from .permissions import is_clinic_admin, is_patient


def clinic_context(request):
    """
    Role flags and the unread-notification count used by the navigation bar
    so menus change depending on who is logged in.
    """
    user = request.user
    context = {
        "clinic_name": "Piki Ora Medical Centre",
        "is_clinic_admin": is_clinic_admin(user),
        "is_patient": is_patient(user),
        "unread_notifications": 0,
    }
    if context["is_patient"]:
        # Imported here to avoid loading models when the app registry starts.
        from clinic.models import Notification

        context["unread_notifications"] = Notification.objects.filter(
            user=user, is_read=False
        ).count()
    return context
