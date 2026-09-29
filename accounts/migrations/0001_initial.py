import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PatientProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "phone",
                    models.CharField(
                        blank=True,
                        max_length=20,
                        validators=[
                            django.core.validators.RegexValidator(
                                message="Enter a valid phone number (digits, spaces, +, - and brackets only).",
                                regex="^\\+?[0-9 ()-]{7,20}$",
                            )
                        ],
                    ),
                ),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="patient_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["user__last_name", "user__first_name"],
            },
        ),
    ]
