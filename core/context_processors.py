from .permissions import is_clinic_admin, is_patient


def clinic_context(request):
    # gives every template the user's role and unread notification count (for the navbar)
    user = request.user
    context = {
        "clinic_name": "Piki Ora Medical Centre",
        "is_clinic_admin": is_clinic_admin(user),
        "is_patient": is_patient(user),
        "unread_notifications": 0,
    }
    if context["is_patient"]:
        # import here so the models aren't loaded too early
        from clinic.models import Notification

        context["unread_notifications"] = Notification.objects.filter(
            user=user, is_read=False
        ).count()
    return context
