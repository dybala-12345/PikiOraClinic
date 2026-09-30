from django.apps import AppConfig


class DashboardConfig(AppConfig):
    # our own admin dashboard (instead of django admin)

    default_auto_field = "django.db.models.BigAutoField"
    name = "dashboard"
    verbose_name = "Administrator dashboard"
