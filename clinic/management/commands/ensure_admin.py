# creates the admin account from env variables (ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PASSWORD)
# needed on render because the free plan has no shell

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the clinic administrator from ADMIN_USERNAME / ADMIN_EMAIL / ADMIN_PASSWORD."

    def handle(self, *args, **options):
        username = os.environ.get("ADMIN_USERNAME")
        password = os.environ.get("ADMIN_PASSWORD")
        email = os.environ.get("ADMIN_EMAIL", "")
        if not username or not password:
            self.stdout.write("ADMIN_USERNAME/ADMIN_PASSWORD not set - skipping admin creation.")
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username, defaults={"email": email})
        user.email = email or user.email
        user.first_name = user.first_name or "Clinic"
        user.last_name = user.last_name or "Administrator"
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Administrator '{username}' {'created' if created else 'updated'}."))
