"""Root URL configuration for the Piki Ora Medical Centre system."""

from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("clinic.urls")),
    path("accounts/", include("accounts.urls")),
    # Login, logout and password-change views provided by Django.
    path("accounts/", include("django.contrib.auth.urls")),
    # Custom administrator dashboard (this is the system's admin interface).
    path("dashboard/", include("dashboard.urls")),
]

# The built-in Django Admin is only available while developing (DEBUG=True)
# for testing. It is switched off on Render and is NOT the system's
# administrator interface - that is the custom dashboard above.
if settings.DEBUG:
    urlpatterns += [path("admin/", admin.site.urls)]
