from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("clinic.urls")),
    path("accounts/", include("accounts.urls")),
    # login / logout / change password (built into django)
    path("accounts/", include("django.contrib.auth.urls")),
    # our admin dashboard
    path("dashboard/", include("dashboard.urls")),
]

# django admin only works when DEBUG is on (just for testing)
# it's off on render - the dashboard is the real admin page
if settings.DEBUG:
    urlpatterns += [path("admin/", admin.site.urls)]
