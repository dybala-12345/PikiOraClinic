from django.apps import AppConfig


class CoreConfig(AppConfig):
    # shared stuff - roles, form styling, template variables

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
