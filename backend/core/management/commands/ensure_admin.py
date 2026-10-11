import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create the initial administrator from environment variables."

    def handle(self, *args, **options):
        email = os.getenv("ADMIN_EMAIL", "").strip()
        password = os.getenv("ADMIN_PASSWORD", "")
        name = os.getenv("ADMIN_NAME", "Administrator").strip()

        if not email or not password:
            self.stdout.write(self.style.WARNING(
                "ADMIN_EMAIL or ADMIN_PASSWORD missing; skipping admin creation."
            ))
            return

        User = get_user_model()
        username_field = User.USERNAME_FIELD
        lookup = {username_field: email}
        user, created = User.objects.get_or_create(
            **lookup,
            defaults={"is_staff": True, "is_superuser": True},
        )

        changed = False
        if not user.is_staff:
            user.is_staff = True
            changed = True
        if not user.is_superuser:
            user.is_superuser = True
            changed = True
        if hasattr(user, "first_name") and name and not user.first_name:
            user.first_name = name
            changed = True

        if created or os.getenv("RESET_ADMIN_PASSWORD", "false").lower() == "true":
            user.set_password(password)
            changed = True

        if changed:
            user.save()

        message = "created" if created else "already exists"
        self.stdout.write(self.style.SUCCESS(f"Admin {email} {message}."))
