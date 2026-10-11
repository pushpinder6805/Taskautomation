from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="workspacemember",
            name="capacity_hours_per_week",
            field=models.DecimalField(decimal_places=2, default=40, max_digits=6),
        ),
        migrations.CreateModel(
            name="Client",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("company", models.CharField(blank=True, max_length=180)),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="clients", to="core.workspace")),
            ],
        ),
        migrations.AddField(model_name="project", name="budget", field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
        migrations.AddField(model_name="project", name="hourly_rate", field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
        migrations.AddField(model_name="project", name="client", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="projects", to="core.client")),
        migrations.AlterField(model_name="task", name="status", field=models.CharField(default="todo", max_length=40)),
        migrations.AddField(model_name="task", name="parent", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="subtasks", to="core.task")),
        migrations.AddField(model_name="task", name="estimate_hours", field=models.DecimalField(blank=True, decimal_places=2, max_digits=7, null=True)),
        migrations.CreateModel(
            name="TaskStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.SlugField(max_length=40)),
                ("name", models.CharField(max_length=80)),
                ("category", models.CharField(choices=[("todo", "To do"), ("active", "Active"), ("review", "Review"), ("done", "Done")], default="todo", max_length=20)),
                ("color", models.CharField(default="#64748b", max_length=20)),
                ("position", models.PositiveIntegerField(default=0)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="statuses", to="core.project")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.AddConstraint(model_name="taskstatus", constraint=models.UniqueConstraint(fields=("project", "key"), name="unique_project_status_key")),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("author", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="task_comments", to=settings.AUTH_USER_MODEL)),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="comments", to="core.task")),
            ],
        ),
        migrations.CreateModel(
            name="Attachment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="task_attachments/%Y/%m/")),
                ("original_name", models.CharField(max_length=255)),
                ("size", models.PositiveBigIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attachments", to="core.task")),
                ("uploaded_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="task_attachments", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Activity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("action", models.CharField(max_length=80)),
                ("detail", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="activities", to=settings.AUTH_USER_MODEL)),
                ("project", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="core.project")),
                ("task", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="core.task")),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="activities", to="core.workspace")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField(blank=True)),
                ("link", models.CharField(blank=True, max_length=255)),
                ("is_read", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="taskautomation_notifications", to=settings.AUTH_USER_MODEL)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notifications", to="core.workspace")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="TimeEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("duration_minutes", models.PositiveIntegerField()),
                ("note", models.CharField(blank=True, max_length=255)),
                ("work_date", models.DateField(default=django.utils.timezone.localdate)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="time_entries", to="core.project")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="time_entries", to="core.task")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="time_entries", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="TaskDependency",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="created_dependencies", to=settings.AUTH_USER_MODEL)),
                ("depends_on", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocking_links", to="core.task")),
                ("task", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="blocked_by_links", to="core.task")),
            ],
        ),
        migrations.AddConstraint(model_name="taskdependency", constraint=models.UniqueConstraint(fields=("task", "depends_on"), name="unique_task_dependency")),
        migrations.CreateModel(
            name="ProjectTemplate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=180)),
                ("description", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="project_templates", to=settings.AUTH_USER_MODEL)),
                ("workspace", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="templates", to="core.workspace")),
            ],
        ),
        migrations.CreateModel(
            name="TemplateTask",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=240)),
                ("description", models.TextField(blank=True)),
                ("priority", models.CharField(choices=[("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")], default="medium", max_length=20)),
                ("relative_due_days", models.PositiveIntegerField(blank=True, null=True)),
                ("position", models.PositiveIntegerField(default=0)),
                ("template", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tasks", to="core.projecttemplate")),
            ],
            options={"ordering": ["position", "id"]},
        ),
        migrations.CreateModel(
            name="ClientAccess",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("token", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ("can_view_tasks", models.BooleanField(default=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("client", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="access_tokens", to="core.client")),
                ("project", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="client_access_tokens", to="core.project")),
            ],
        ),
    ]
