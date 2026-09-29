from django.apps import AppConfig


class DashboardConfig(AppConfig):
    """Custom administrator dashboard (replaces Django Admin for staff)."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"
    verbose_name = "Administrator dashboard"
