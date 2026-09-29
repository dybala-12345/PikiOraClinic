from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Shared helpers: role checks, form styling, template context."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
