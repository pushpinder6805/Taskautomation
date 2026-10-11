import os
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or synchronize the administrator from environment variables."

    def handle(self, *args, **options):
        email = os.getenv("ADMIN_EMAIL", "").strip()
        password = os.getenv("ADMIN_PASSWORD", "")
        name = os.getenv("ADMIN_NAME", "Administrator").strip()

        if not email or not password:
            raise CommandError("ADMIN_EMAIL and ADMIN_PASSWORD are required.")

        User = get_user_model()
        username_field = User.USERNAME_FIELD

        # The installer uses the administrator email as the login identifier.
        # Prefer an existing account with this login. For Django's default User
        # model, also recover an account that may already have the same email.
        lookup = {username_field: email}
        user = User.objects.filter(**lookup).first()

        if user is None and hasattr(User, "email"):
            user = User.objects.filter(email__iexact=email).first()

        created = user is None
        if created:
            user = User(**lookup)
        else:
            setattr(user, username_field, email)

        # Keep installer credentials authoritative. This prevents an old
        # database volume from retaining a stale admin password after a
        # reinstall or reconfiguration.
        if hasattr(user, "email"):
            user.email = email
        if hasattr(user, "first_name"):
            user.first_name = name

        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save()

        action = "created" if created else "synchronized"
        self.stdout.write(
            self.style.SUCCESS(
                f"Administrator {email} {action}. Login username: {email}"
            )
        )
