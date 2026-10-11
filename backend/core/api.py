import csv
from datetime import timedelta
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q, Sum
from django.http import FileResponse, HttpResponse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import (
    Activity, Attachment, Client, ClientAccess, Comment, Invitation, Notification,
    Project, ProjectMember, ProjectTemplate, Task, TaskDependency, TaskStatus,
    TemplateTask, TimeEntry, Workspace, WorkspaceMember,
)

User = get_user_model()

DEFAULT_STATUSES = [
    ("todo", "To do", "todo", "#94a3b8"),
    ("in_progress", "In progress", "active", "#6366f1"),
    ("review", "Review", "review", "#f59e0b"),
    ("done", "Done", "done", "#22c55e"),
]


def user_json(user):
    return {"id": user.id, "name": (user.get_full_name() or user.username).strip(), "email": user.email or user.username}


def ensure_workspace(user):
    membership = WorkspaceMember.objects.filter(user=user).select_related("workspace").first()
    if membership:
        return membership.workspace
    workspace = Workspace.objects.create(name=f"{(user.first_name or 'My').strip()} Workspace", owner=user)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role="owner")
    return workspace


def ensure_statuses(project):
    if not project.statuses.exists():
        for position, (key, name, category, color) in enumerate(DEFAULT_STATUSES):
            TaskStatus.objects.create(project=project, key=key, name=name, category=category, color=color, position=position)
    return project.statuses.all()


def status_json(item):
    return {"id": item.id, "key": item.key, "name": item.name, "category": item.category, "color": item.color, "position": item.position}


def project_json(project):
    ensure_statuses(project)
    top_tasks = project.tasks.filter(parent__isnull=True)
    return {
        "id": project.id, "name": project.name, "description": project.description, "status": project.status,
        "start_date": project.start_date, "end_date": project.end_date, "progress": project.progress,
        "task_count": top_tasks.count(), "completed_count": sum(1 for t in top_tasks if t.status in set(project.statuses.filter(category="done").values_list("key", flat=True))),
        "members": [user_json(user) for user in project.members.all()], "statuses": [status_json(s) for s in project.statuses.all()],
        "budget": project.budget, "hourly_rate": project.hourly_rate, "tracked_hours": project.tracked_hours,
        "client": {"id": project.client_id, "name": project.client.name} if project.client else None,
    }


def task_json(task, detail=False):
    data = {
        "id": task.id, "project_id": task.project_id, "project_name": task.project.name,
        "parent_id": task.parent_id, "title": task.title, "description": task.description,
        "status": task.status, "priority": task.priority, "start_date": task.start_date, "due_date": task.due_date,
        "estimate_hours": task.estimate_hours, "assignees": [user_json(user) for user in task.assignees.all()],
        "subtask_count": task.subtasks.count(), "completed_subtasks": task.subtasks.filter(status__in=task.project.statuses.filter(category="done").values("key")).count(),
        "comment_count": task.comments.count(), "attachment_count": task.attachments.count(),
        "tracked_minutes": task.time_entries.aggregate(total=Sum("duration_minutes"))["total"] or 0,
    }
    if detail:
        data.update({
            "subtasks": [task_json(x) for x in task.subtasks.select_related("project").prefetch_related("assignees")],
            "comments": [{"id": c.id, "body": c.body, "author": user_json(c.author), "created_at": c.created_at} for c in task.comments.select_related("author").all()],
            "attachments": [{"id": a.id, "name": a.original_name, "size": a.size, "created_at": a.created_at, "uploaded_by": user_json(a.uploaded_by)} for a in task.attachments.select_related("uploaded_by").all()],
            "dependencies": [{"id": d.id, "task": {"id": d.depends_on_id, "title": d.depends_on.title, "status": d.depends_on.status}} for d in task.blocked_by_links.select_related("depends_on").all()],
            "time_entries": [{"id": e.id, "minutes": e.duration_minutes, "note": e.note, "work_date": e.work_date, "user": user_json(e.user)} for e in task.time_entries.select_related("user").order_by("-work_date", "-id")],
            "activity": [{"id": a.id, "action": a.action, "detail": a.detail, "actor": user_json(a.actor) if a.actor else None, "created_at": a.created_at} for a in task.activities.select_related("actor")[:50]],
        })
    return data


def log_activity(workspace, actor, action, detail="", project=None, task=None):
    return Activity.objects.create(workspace=workspace, actor=actor, action=action, detail=detail, project=project, task=task)


def notify(users, workspace, title, message="", link=""):
    for user in users:
        Notification.objects.create(user=user, workspace=workspace, title=title, message=message, link=link)


def workspace_task(request, task_id):
    workspace = ensure_workspace(request.user)
    return workspace, Task.objects.filter(id=task_id, project__workspace=workspace).select_related("project").prefetch_related("assignees").first()


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = (request.data.get("email") or request.data.get("username") or "").strip()
    user = authenticate(username=username, password=request.data.get("password") or "")
    if not user:
        return Response({"detail": "Invalid email or password."}, status=400)
    token, _ = Token.objects.get_or_create(user=user)
    ensure_workspace(user)
    return Response({"token": token.key, "user": user_json(user)})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def me_view(request):
    workspace = ensure_workspace(request.user)
    membership = WorkspaceMember.objects.get(workspace=workspace, user=request.user)
    return Response({"user": user_json(request.user), "workspace": {"id": workspace.id, "name": workspace.name, "role": membership.role}})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def dashboard_view(request):
    workspace = ensure_workspace(request.user)
    projects = Project.objects.filter(workspace=workspace).prefetch_related("tasks", "members", "statuses")
    tasks = Task.objects.filter(project__workspace=workspace, parent__isnull=True).select_related("project").prefetch_related("assignees")
    done_keys = set(TaskStatus.objects.filter(project__workspace=workspace, category="done").values_list("key", flat=True)) | {"done"}
    completed = tasks.filter(status__in=done_keys).count()
    return Response({
        "stats": {"projects": projects.count(), "tasks": tasks.count(), "completed": completed,
                  "overdue": tasks.exclude(status__in=done_keys).filter(due_date__lt=timezone.localdate()).count(),
                  "members": WorkspaceMember.objects.filter(workspace=workspace).count()},
        "projects": [project_json(p) for p in projects.order_by("-created_at")[:6]],
        "my_tasks": [task_json(t) for t in tasks.filter(Q(assignees=request.user) | Q(created_by=request.user)).distinct()[:10]],
    })


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def projects_view(request):
    workspace = ensure_workspace(request.user)
    if request.method == "GET":
        return Response([project_json(p) for p in Project.objects.filter(workspace=workspace).prefetch_related("tasks", "members", "statuses", "client").order_by("-created_at")])
    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"detail": "Project name is required."}, status=400)
    client = Client.objects.filter(id=request.data.get("client_id"), workspace=workspace).first() if request.data.get("client_id") else None
    project = Project.objects.create(workspace=workspace, name=name, description=request.data.get("description") or "",
        start_date=request.data.get("start_date") or None, end_date=request.data.get("end_date") or None,
        budget=request.data.get("budget") or None, hourly_rate=request.data.get("hourly_rate") or None,
        client=client, created_by=request.user)
    ensure_statuses(project)
    ProjectMember.objects.get_or_create(project=project, user=request.user)
    for user_id in request.data.get("member_ids") or []:
        if WorkspaceMember.objects.filter(workspace=workspace, user_id=user_id).exists(): ProjectMember.objects.get_or_create(project=project, user_id=user_id)
    log_activity(workspace, request.user, "project_created", f"Created project {project.name}", project=project)
    return Response(project_json(project), status=201)


@api_view(["GET", "PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def project_detail_view(request, project_id):
    workspace = ensure_workspace(request.user)
    project = Project.objects.filter(id=project_id, workspace=workspace).prefetch_related("tasks", "members", "statuses").first()
    if not project: return Response({"detail": "Project not found."}, status=404)
    if request.method == "DELETE":
        project.delete(); return Response(status=204)
    if request.method == "PATCH":
        for field in ["name", "description", "status"]:
            if field in request.data: setattr(project, field, request.data.get(field))
        for field in ["start_date", "end_date", "budget", "hourly_rate"]:
            if field in request.data: setattr(project, field, request.data.get(field) or None)
        if "client_id" in request.data:
            project.client = Client.objects.filter(id=request.data.get("client_id"), workspace=workspace).first() if request.data.get("client_id") else None
        project.save(); log_activity(workspace, request.user, "project_updated", "Project details updated", project=project)
    return Response(project_json(project))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def project_statuses_view(request, project_id):
    workspace = ensure_workspace(request.user)
    project = Project.objects.filter(id=project_id, workspace=workspace).first()
    if not project: return Response({"detail": "Project not found."}, status=404)
    ensure_statuses(project)
    if request.method == "GET": return Response([status_json(x) for x in project.statuses.all()])
    name = (request.data.get("name") or "").strip()
    if not name: return Response({"detail": "Status name is required."}, status=400)
    base = "-".join(name.lower().split())[:32] or "status"; key = base; i = 2
    while project.statuses.filter(key=key).exists(): key = f"{base}-{i}"; i += 1
    item = TaskStatus.objects.create(project=project, key=key, name=name, category=request.data.get("category") or "active",
        color=request.data.get("color") or "#64748b", position=project.statuses.count())
    log_activity(workspace, request.user, "status_created", f"Added workflow status {name}", project=project)
    return Response(status_json(item), status=201)


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def status_detail_view(request, status_id):
    workspace = ensure_workspace(request.user)
    item = TaskStatus.objects.filter(id=status_id, project__workspace=workspace).first()
    if not item: return Response({"detail": "Status not found."}, status=404)
    if request.method == "DELETE":
        fallback = item.project.statuses.exclude(id=item.id).order_by("position").first()
        if not fallback: return Response({"detail": "A project must have at least one status."}, status=400)
        item.project.tasks.filter(status=item.key).update(status=fallback.key); item.delete(); return Response(status=204)
    for f in ["name", "category", "color", "position"]:
        if f in request.data: setattr(item, f, request.data.get(f))
    item.save(); return Response(status_json(item))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def tasks_view(request):
    workspace = ensure_workspace(request.user)
    if request.method == "GET":
        qs = Task.objects.filter(project__workspace=workspace).select_related("project").prefetch_related("assignees", "project__statuses")
        if request.query_params.get("project"): qs = qs.filter(project_id=request.query_params.get("project"))
        if request.query_params.get("parent") == "root": qs = qs.filter(parent__isnull=True)
        return Response([task_json(t) for t in qs])
    project = Project.objects.filter(id=request.data.get("project_id"), workspace=workspace).first()
    if not project: return Response({"detail": "A valid project is required."}, status=400)
    ensure_statuses(project)
    title = (request.data.get("title") or "").strip()
    if not title: return Response({"detail": "Task title is required."}, status=400)
    parent = Task.objects.filter(id=request.data.get("parent_id"), project=project).first() if request.data.get("parent_id") else None
    status_key = request.data.get("status") or project.statuses.order_by("position").first().key
    if not project.statuses.filter(key=status_key).exists(): return Response({"detail": "Invalid project status."}, status=400)
    task = Task.objects.create(project=project, parent=parent, title=title, description=request.data.get("description") or "",
        status=status_key, priority=request.data.get("priority") or "medium", start_date=request.data.get("start_date") or None,
        due_date=request.data.get("due_date") or None, estimate_hours=request.data.get("estimate_hours") or None, created_by=request.user)
    allowed = WorkspaceMember.objects.filter(workspace=workspace, user_id__in=request.data.get("assignee_ids") or []).values_list("user_id", flat=True)
    task.assignees.set(allowed)
    ProjectMember.objects.get_or_create(project=project, user=request.user)
    log_activity(workspace, request.user, "subtask_created" if parent else "task_created", task.title, project=project, task=task)
    notify(task.assignees.exclude(id=request.user.id), workspace, "Task assigned", task.title, f"task:{task.id}")
    return Response(task_json(task), status=201)


@api_view(["GET", "PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def task_detail_view(request, task_id):
    workspace, task = workspace_task(request, task_id)
    if not task: return Response({"detail": "Task not found."}, status=404)
    if request.method == "GET": return Response(task_json(task, True))
    if request.method == "DELETE": task.delete(); return Response(status=204)
    old_status = task.status
    for f in ["title", "description", "priority"]:
        if f in request.data: setattr(task, f, request.data.get(f))
    if "status" in request.data:
        if not task.project.statuses.filter(key=request.data.get("status")).exists(): return Response({"detail": "Invalid project status."}, status=400)
        task.status = request.data.get("status")
    for f in ["start_date", "due_date", "estimate_hours"]:
        if f in request.data: setattr(task, f, request.data.get(f) or None)
    if "assignee_ids" in request.data:
        allowed = WorkspaceMember.objects.filter(workspace=workspace, user_id__in=request.data.get("assignee_ids") or []).values_list("user_id", flat=True)
        task.assignees.set(allowed)
    task.save()
    action = "status_changed" if task.status != old_status else "task_updated"
    log_activity(workspace, request.user, action, f"{old_status} → {task.status}" if action == "status_changed" else task.title, project=task.project, task=task)
    return Response(task_json(task, True))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def comments_view(request, task_id):
    workspace, task = workspace_task(request, task_id)
    if not task: return Response({"detail": "Task not found."}, status=404)
    if request.method == "GET": return Response(task_json(task, True)["comments"])
    body = (request.data.get("body") or "").strip()
    if not body: return Response({"detail": "Comment cannot be empty."}, status=400)
    comment = Comment.objects.create(task=task, author=request.user, body=body)
    log_activity(workspace, request.user, "comment_added", body[:140], project=task.project, task=task)
    notify(task.assignees.exclude(id=request.user.id), workspace, "New task comment", task.title, f"task:{task.id}")
    return Response({"id": comment.id, "body": comment.body, "author": user_json(request.user), "created_at": comment.created_at}, status=201)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def attachments_view(request, task_id):
    workspace, task = workspace_task(request, task_id)
    if not task: return Response({"detail": "Task not found."}, status=404)
    if request.method == "GET": return Response(task_json(task, True)["attachments"])
    upload = request.FILES.get("file")
    if not upload: return Response({"detail": "Choose a file to upload."}, status=400)
    if upload.size > 25 * 1024 * 1024: return Response({"detail": "Maximum attachment size is 25 MB."}, status=400)
    item = Attachment.objects.create(task=task, uploaded_by=request.user, file=upload, original_name=upload.name[:255], size=upload.size)
    log_activity(workspace, request.user, "attachment_added", item.original_name, project=task.project, task=task)
    return Response({"id": item.id, "name": item.original_name, "size": item.size, "created_at": item.created_at}, status=201)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def attachment_download_view(request, attachment_id):
    workspace = ensure_workspace(request.user)
    item = Attachment.objects.filter(id=attachment_id, task__project__workspace=workspace).first()
    if not item: return Response({"detail": "Attachment not found."}, status=404)
    return FileResponse(item.file.open("rb"), as_attachment=True, filename=item.original_name)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def time_entries_view(request, task_id):
    workspace, task = workspace_task(request, task_id)
    if not task: return Response({"detail": "Task not found."}, status=404)
    if request.method == "GET": return Response(task_json(task, True)["time_entries"])
    minutes = int(request.data.get("minutes") or 0)
    if minutes <= 0: return Response({"detail": "Minutes must be greater than zero."}, status=400)
    entry = TimeEntry.objects.create(task=task, project=task.project, user=request.user, duration_minutes=minutes,
        note=request.data.get("note") or "", work_date=request.data.get("work_date") or timezone.localdate())
    log_activity(workspace, request.user, "time_logged", f"{minutes} minutes", project=task.project, task=task)
    return Response({"id": entry.id, "minutes": entry.duration_minutes, "note": entry.note, "work_date": entry.work_date, "user": user_json(request.user)}, status=201)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def dependencies_view(request, task_id):
    workspace, task = workspace_task(request, task_id)
    if not task: return Response({"detail": "Task not found."}, status=404)
    if request.method == "GET": return Response(task_json(task, True)["dependencies"])
    depends_on = Task.objects.filter(id=request.data.get("depends_on_id"), project=task.project).first()
    if not depends_on or depends_on.id == task.id: return Response({"detail": "Choose another task from this project."}, status=400)
    link, created = TaskDependency.objects.get_or_create(task=task, depends_on=depends_on, defaults={"created_by": request.user})
    if created: log_activity(workspace, request.user, "dependency_added", depends_on.title, project=task.project, task=task)
    return Response({"id": link.id, "task": {"id": depends_on.id, "title": depends_on.title, "status": depends_on.status}}, status=201)


@api_view(["DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def dependency_detail_view(request, dependency_id):
    workspace = ensure_workspace(request.user)
    link = TaskDependency.objects.filter(id=dependency_id, task__project__workspace=workspace).first()
    if not link: return Response({"detail": "Dependency not found."}, status=404)
    link.delete(); return Response(status=204)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def members_view(request):
    workspace = ensure_workspace(request.user)
    if request.method == "GET":
        members = WorkspaceMember.objects.filter(workspace=workspace).select_related("user")
        invitations = Invitation.objects.filter(workspace=workspace, accepted_at__isnull=True).order_by("-created_at")
        return Response({"members": [{**user_json(m.user), "role": m.role, "capacity_hours_per_week": m.capacity_hours_per_week} for m in members],
                         "invitations": [{"id": x.id, "email": x.email, "role": x.role, "token": str(x.token)} for x in invitations]})
    current = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).first()
    if not current or current.role not in ["owner", "admin"]: return Response({"detail": "Only workspace admins can invite members."}, status=403)
    email = (request.data.get("email") or "").strip().lower()
    if not email: return Response({"detail": "Email is required."}, status=400)
    role = request.data.get("role") if request.data.get("role") in ["admin", "member"] else "member"
    invite = Invitation.objects.filter(workspace=workspace, email__iexact=email, accepted_at__isnull=True).first() or Invitation.objects.create(workspace=workspace, email=email, role=role, invited_by=request.user)
    invite_url = f"{request.build_absolute_uri('/').rstrip('/')}/?invite={invite.token}"
    try: send_mail(f"You're invited to {workspace.name}", f"Join {workspace.name}: {invite_url}", None, [email], fail_silently=True)
    except Exception: pass
    return Response({"id": invite.id, "email": invite.email, "role": invite.role, "invite_url": invite_url}, status=201)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def accept_invitation_view(request, token):
    invite = Invitation.objects.filter(token=token, accepted_at__isnull=True).select_related("workspace").first()
    if not invite: return Response({"detail": "Invitation is invalid or already used."}, status=404)
    if request.method == "GET": return Response({"email": invite.email, "workspace": invite.workspace.name, "role": invite.role})
    password = request.data.get("password") or ""; name = (request.data.get("name") or "").strip()
    if len(password) < 8: return Response({"detail": "Password must be at least 8 characters."}, status=400)
    user = User.objects.filter(username__iexact=invite.email).first()
    if not user: user = User.objects.create_user(username=invite.email, email=invite.email, password=password)
    else: user.set_password(password)
    if name: user.first_name = name
    user.email = invite.email; user.save()
    WorkspaceMember.objects.get_or_create(workspace=invite.workspace, user=user, defaults={"role": invite.role})
    invite.accepted_at = timezone.now(); invite.save(update_fields=["accepted_at"])
    token_obj, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token_obj.key, "user": user_json(user)})


@api_view(["GET", "PATCH"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def notifications_view(request):
    workspace = ensure_workspace(request.user)
    qs = Notification.objects.filter(workspace=workspace, user=request.user)
    if request.method == "PATCH": qs.filter(is_read=False).update(is_read=True)
    return Response({"unread": qs.filter(is_read=False).count(), "items": [{"id": n.id, "title": n.title, "message": n.message, "link": n.link, "is_read": n.is_read, "created_at": n.created_at} for n in qs[:50]]})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def activity_view(request):
    workspace = ensure_workspace(request.user)
    qs = Activity.objects.filter(workspace=workspace).select_related("actor", "project", "task")
    if request.query_params.get("project"): qs = qs.filter(project_id=request.query_params.get("project"))
    if request.query_params.get("task"): qs = qs.filter(task_id=request.query_params.get("task"))
    return Response([{"id": a.id, "action": a.action, "detail": a.detail, "actor": user_json(a.actor) if a.actor else None,
                      "project_id": a.project_id, "task_id": a.task_id, "created_at": a.created_at} for a in qs[:100]])


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def workload_view(request):
    workspace = ensure_workspace(request.user)
    result = []
    for membership in WorkspaceMember.objects.filter(workspace=workspace).select_related("user"):
        tasks = Task.objects.filter(project__workspace=workspace, assignees=membership.user).distinct()
        planned = sum(float(v or 0) for v in tasks.values_list("estimate_hours", flat=True))
        tracked = (TimeEntry.objects.filter(project__workspace=workspace, user=membership.user).aggregate(total=Sum("duration_minutes"))["total"] or 0) / 60
        result.append({**user_json(membership.user), "capacity": float(membership.capacity_hours_per_week), "planned_hours": round(planned, 2),
                       "tracked_hours": round(tracked, 2), "task_count": tasks.count()})
    return Response(result)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def reports_view(request):
    workspace = ensure_workspace(request.user)
    projects = Project.objects.filter(workspace=workspace).prefetch_related("statuses", "tasks")
    output = []
    for p in projects:
        tracked = p.time_entries.aggregate(total=Sum("duration_minutes"))["total"] or 0
        labor_cost = float(tracked) / 60 * float(p.hourly_rate or 0)
        budget = float(p.budget or 0)
        output.append({"id": p.id, "name": p.name, "progress": p.progress, "tasks": p.tasks.filter(parent__isnull=True).count(),
                       "tracked_hours": round(float(tracked) / 60, 2), "budget": budget, "labor_value": round(labor_cost, 2),
                       "remaining_budget": round(budget - labor_cost, 2) if p.budget is not None else None})
    return Response(output)


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def calendar_view(request):
    workspace = ensure_workspace(request.user)
    qs = Task.objects.filter(project__workspace=workspace).exclude(Q(start_date__isnull=True) & Q(due_date__isnull=True)).select_related("project")
    return Response([{"id": t.id, "title": t.title, "project": t.project.name, "start_date": t.start_date, "due_date": t.due_date, "status": t.status} for t in qs])


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def templates_view(request):
    workspace = ensure_workspace(request.user)
    if request.method == "GET":
        return Response([{"id": x.id, "name": x.name, "description": x.description, "tasks": [{"id": t.id, "title": t.title, "priority": t.priority, "relative_due_days": t.relative_due_days} for t in x.tasks.all()]} for x in ProjectTemplate.objects.filter(workspace=workspace).prefetch_related("tasks")])
    source = Project.objects.filter(id=request.data.get("source_project_id"), workspace=workspace).first()
    name = (request.data.get("name") or (f"{source.name} template" if source else "")).strip()
    if not name: return Response({"detail": "Template name is required."}, status=400)
    template = ProjectTemplate.objects.create(workspace=workspace, name=name, description=request.data.get("description") or "", created_by=request.user)
    if source:
        for i, t in enumerate(source.tasks.filter(parent__isnull=True).order_by("created_at")):
            delta = (t.due_date - source.start_date).days if t.due_date and source.start_date and t.due_date >= source.start_date else None
            TemplateTask.objects.create(template=template, title=t.title, description=t.description, priority=t.priority, relative_due_days=delta, position=i)
    return Response({"id": template.id, "name": template.name, "description": template.description, "tasks": []}, status=201)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def template_apply_view(request, template_id):
    workspace = ensure_workspace(request.user)
    template = ProjectTemplate.objects.filter(id=template_id, workspace=workspace).prefetch_related("tasks").first()
    if not template: return Response({"detail": "Template not found."}, status=404)
    name = (request.data.get("name") or "").strip()
    if not name: return Response({"detail": "Project name is required."}, status=400)
    start = request.data.get("start_date") or timezone.localdate()
    if isinstance(start, str): start = timezone.datetime.strptime(start, "%Y-%m-%d").date()
    with transaction.atomic():
        project = Project.objects.create(workspace=workspace, name=name, description=template.description, start_date=start, created_by=request.user)
        ProjectMember.objects.create(project=project, user=request.user); ensure_statuses(project)
        for t in template.tasks.all():
            Task.objects.create(project=project, title=t.title, description=t.description, priority=t.priority,
                due_date=start + timedelta(days=t.relative_due_days) if t.relative_due_days is not None else None, created_by=request.user)
    return Response(project_json(project), status=201)


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def clients_view(request):
    workspace = ensure_workspace(request.user)
    if request.method == "GET": return Response([{"id": c.id, "name": c.name, "email": c.email, "company": c.company, "notes": c.notes} for c in Client.objects.filter(workspace=workspace)])
    name = (request.data.get("name") or "").strip()
    if not name: return Response({"detail": "Client name is required."}, status=400)
    c = Client.objects.create(workspace=workspace, name=name, email=request.data.get("email") or "", company=request.data.get("company") or "", notes=request.data.get("notes") or "")
    return Response({"id": c.id, "name": c.name, "email": c.email, "company": c.company, "notes": c.notes}, status=201)


@api_view(["POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def client_access_view(request, project_id):
    workspace = ensure_workspace(request.user)
    project = Project.objects.filter(id=project_id, workspace=workspace).select_related("client").first()
    if not project or not project.client: return Response({"detail": "Assign a client to this project first."}, status=400)
    token = ClientAccess.objects.filter(project=project, client=project.client, is_active=True).first() or ClientAccess.objects.create(project=project, client=project.client)
    url = f"{request.build_absolute_uri('/').rstrip('/')}/?client={token.token}"
    return Response({"token": str(token.token), "url": url})


@api_view(["GET"])
@permission_classes([AllowAny])
def client_portal_view(request, token):
    access = ClientAccess.objects.filter(token=token, is_active=True).select_related("project", "client").first()
    if not access: return Response({"detail": "Client link is invalid."}, status=404)
    p = access.project; ensure_statuses(p)
    tasks = p.tasks.filter(parent__isnull=True).select_related("project").prefetch_related("assignees") if access.can_view_tasks else []
    return Response({"client": {"name": access.client.name, "company": access.client.company}, "project": project_json(p), "tasks": [task_json(t) for t in tasks]})


@api_view(["GET"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def export_tasks_view(request):
    workspace = ensure_workspace(request.user)
    response = HttpResponse(content_type="text/csv"); response["Content-Disposition"] = 'attachment; filename="tasks.csv"'
    writer = csv.writer(response); writer.writerow(["Project", "Task", "Status", "Priority", "Start", "Due", "Assignees", "Estimate hours"])
    for t in Task.objects.filter(project__workspace=workspace).select_related("project").prefetch_related("assignees"):
        writer.writerow([t.project.name, t.title, t.status, t.priority, t.start_date or "", t.due_date or "", ", ".join(u.email or u.username for u in t.assignees.all()), t.estimate_hours or ""])
    return response
