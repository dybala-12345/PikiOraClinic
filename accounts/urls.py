from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("after-login/", views.after_login, name="after_login"),
    path("profile/", views.profile, name="profile"),
]
