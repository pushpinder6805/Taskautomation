import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Workspace(models.Model):
    name = models.CharField(max_length=160)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_workspaces")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class WorkspaceMember(models.Model):
    ROLE_CHOICES = [("owner", "Owner"), ("admin", "Admin"), ("member", "Member")]
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="workspace_memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    capacity_hours_per_week = models.DecimalField(max_digits=6, decimal_places=2, default=40)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "user"], name="unique_workspace_member")]


class Invitation(models.Model):
    ROLE_CHOICES = [("admin", "Admin"), ("member", "Member")]
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="member")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_invitations")
    accepted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Client(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=180)
    email = models.EmailField(blank=True)
    company = models.CharField(max_length=180, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Project(models.Model):
    STATUS_CHOICES = [("active", "Active"), ("on_hold", "On hold"), ("completed", "Completed")]
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_projects")
    members = models.ManyToManyField(settings.AUTH_USER_MODEL, through="ProjectMember", related_name="projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def progress(self):
        top_level = self.tasks.filter(parent__isnull=True)
        total = top_level.count()
        if not total:
            return 0
        done_keys = list(self.statuses.filter(category="done").values_list("key", flat=True)) or ["done"]
        return round(top_level.filter(status__in=done_keys).count() * 100 / total)

    @property
    def tracked_hours(self):
        return round(sum(float(x.duration_minutes) for x in self.time_entries.all()) / 60, 2)


class ProjectMember(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_memberships")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="unique_project_member")]


class TaskStatus(models.Model):
    CATEGORY_CHOICES = [("todo", "To do"), ("active", "Active"), ("review", "Review"), ("done", "Done")]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="statuses")
    key = models.SlugField(max_length=40)
    name = models.CharField(max_length=80)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="todo")
    color = models.CharField(max_length=20, default="#64748b")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["project", "key"], name="unique_project_status_key")]


class Task(models.Model):
    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High"), ("urgent", "Urgent")]
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="tasks")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, null=True, blank=True, related_name="subtasks")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=40, default="todo")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    estimate_hours = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    assignees = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="assigned_tasks")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_tasks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class Comment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Attachment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="attachments")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="task_attachments")
    file = models.FileField(upload_to="task_attachments/%Y/%m/")
    original_name = models.CharField(max_length=255)
    size = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class Activity(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="activities")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, null=True, blank=True, related_name="activities")
    task = models.ForeignKey(Task, on_delete=models.CASCADE, null=True, blank=True, related_name="activities")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="activities")
    action = models.CharField(max_length=80)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="taskautomation_notifications")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=180)
    message = models.TextField(blank=True)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TimeEntry(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="time_entries")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="time_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="time_entries")
    duration_minutes = models.PositiveIntegerField()
    note = models.CharField(max_length=255, blank=True)
    work_date = models.DateField(default=timezone.localdate)
    created_at = models.DateTimeField(auto_now_add=True)


class TaskDependency(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="blocked_by_links")
    depends_on = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="blocking_links")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_dependencies")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["task", "depends_on"], name="unique_task_dependency")]


class ProjectTemplate(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="templates")
    name = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="project_templates")
    created_at = models.DateTimeField(auto_now_add=True)


class TemplateTask(models.Model):
    template = models.ForeignKey(ProjectTemplate, on_delete=models.CASCADE, related_name="tasks")
    title = models.CharField(max_length=240)
    description = models.TextField(blank=True)
    priority = models.CharField(max_length=20, choices=Task.PRIORITY_CHOICES, default="medium")
    relative_due_days = models.PositiveIntegerField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class ClientAccess(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="client_access_tokens")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="access_tokens")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    can_view_tasks = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
