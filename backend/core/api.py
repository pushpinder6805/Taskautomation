from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.mail import send_mail
from django.db.models import Count, Q
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Invitation, Project, ProjectMember, Task, Workspace, WorkspaceMember

User = get_user_model()


def user_json(user):
    return {
        "id": user.id,
        "name": (user.get_full_name() or user.username).strip(),
        "email": user.email or user.username,
    }


def ensure_workspace(user):
    membership = WorkspaceMember.objects.filter(user=user).select_related("workspace").first()
    if membership:
        return membership.workspace
    workspace = Workspace.objects.create(name=f"{(user.first_name or 'My').strip()} Workspace", owner=user)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role="owner")
    return workspace


def project_json(project):
    tasks = list(project.tasks.all())
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "start_date": project.start_date,
        "end_date": project.end_date,
        "progress": project.progress,
        "task_count": len(tasks),
        "completed_count": sum(1 for task in tasks if task.status == "done"),
        "members": [user_json(user) for user in project.members.all()],
    }


def task_json(task):
    return {
        "id": task.id,
        "project_id": task.project_id,
        "project_name": task.project.name,
        "title": task.title,
        "description": task.description,
        "status": task.status,
        "priority": task.priority,
        "start_date": task.start_date,
        "due_date": task.due_date,
        "assignees": [user_json(user) for user in task.assignees.all()],
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = (request.data.get("email") or request.data.get("username") or "").strip()
    password = request.data.get("password") or ""
    user = authenticate(username=username, password=password)
    if not user:
        return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
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
    projects = Project.objects.filter(workspace=workspace).prefetch_related("tasks", "members")
    tasks = Task.objects.filter(project__workspace=workspace).select_related("project").prefetch_related("assignees")
    completed = tasks.filter(status="done").count()
    return Response({
        "stats": {
            "projects": projects.count(),
            "tasks": tasks.count(),
            "completed": completed,
            "overdue": tasks.exclude(status="done").filter(due_date__lt=timezone.localdate()).count(),
            "members": WorkspaceMember.objects.filter(workspace=workspace).count(),
        },
        "projects": [project_json(project) for project in projects.order_by("-created_at")[:6]],
        "my_tasks": [task_json(task) for task in tasks.filter(Q(assignees=request.user) | Q(created_by=request.user)).distinct()[:10]],
    })


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def projects_view(request):
    workspace = ensure_workspace(request.user)
    if request.method == "GET":
        projects = Project.objects.filter(workspace=workspace).prefetch_related("tasks", "members").order_by("-created_at")
        return Response([project_json(project) for project in projects])

    name = (request.data.get("name") or "").strip()
    if not name:
        return Response({"detail": "Project name is required."}, status=400)
    project = Project.objects.create(
        workspace=workspace,
        name=name,
        description=request.data.get("description") or "",
        start_date=request.data.get("start_date") or None,
        end_date=request.data.get("end_date") or None,
        created_by=request.user,
    )
    ProjectMember.objects.get_or_create(project=project, user=request.user)
    for user_id in request.data.get("member_ids") or []:
        membership = WorkspaceMember.objects.filter(workspace=workspace, user_id=user_id).first()
        if membership:
            ProjectMember.objects.get_or_create(project=project, user_id=user_id)
    return Response(project_json(project), status=201)


@api_view(["GET", "PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def project_detail_view(request, project_id):
    workspace = ensure_workspace(request.user)
    project = Project.objects.filter(id=project_id, workspace=workspace).prefetch_related("tasks", "members").first()
    if not project:
        return Response({"detail": "Project not found."}, status=404)
    if request.method == "DELETE":
        project.delete()
        return Response(status=204)
    if request.method == "PATCH":
        for field in ["name", "description", "status", "start_date", "end_date"]:
            if field in request.data:
                setattr(project, field, request.data.get(field) or None if field in ["start_date", "end_date"] else request.data.get(field))
        project.save()
    return Response(project_json(project))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def tasks_view(request):
    workspace = ensure_workspace(request.user)
    if request.method == "GET":
        qs = Task.objects.filter(project__workspace=workspace).select_related("project").prefetch_related("assignees")
        project_id = request.query_params.get("project")
        if project_id:
            qs = qs.filter(project_id=project_id)
        return Response([task_json(task) for task in qs])

    project = Project.objects.filter(id=request.data.get("project_id"), workspace=workspace).first()
    if not project:
        return Response({"detail": "A valid project is required."}, status=400)
    title = (request.data.get("title") or "").strip()
    if not title:
        return Response({"detail": "Task title is required."}, status=400)
    task = Task.objects.create(
        project=project,
        title=title,
        description=request.data.get("description") or "",
        status=request.data.get("status") or "todo",
        priority=request.data.get("priority") or "medium",
        start_date=request.data.get("start_date") or None,
        due_date=request.data.get("due_date") or None,
        created_by=request.user,
    )
    member_ids = request.data.get("assignee_ids") or []
    allowed_ids = WorkspaceMember.objects.filter(workspace=workspace, user_id__in=member_ids).values_list("user_id", flat=True)
    task.assignees.set(allowed_ids)
    return Response(task_json(task), status=201)


@api_view(["PATCH", "DELETE"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def task_detail_view(request, task_id):
    workspace = ensure_workspace(request.user)
    task = Task.objects.filter(id=task_id, project__workspace=workspace).select_related("project").prefetch_related("assignees").first()
    if not task:
        return Response({"detail": "Task not found."}, status=404)
    if request.method == "DELETE":
        task.delete()
        return Response(status=204)
    for field in ["title", "description", "status", "priority", "start_date", "due_date"]:
        if field in request.data:
            value = request.data.get(field)
            if field in ["start_date", "due_date"] and not value:
                value = None
            setattr(task, field, value)
    if "assignee_ids" in request.data:
        allowed_ids = WorkspaceMember.objects.filter(workspace=workspace, user_id__in=request.data.get("assignee_ids") or []).values_list("user_id", flat=True)
        task.assignees.set(allowed_ids)
    task.save()
    return Response(task_json(task))


@api_view(["GET", "POST"])
@authentication_classes([TokenAuthentication])
@permission_classes([IsAuthenticated])
def members_view(request):
    workspace = ensure_workspace(request.user)
    if request.method == "GET":
        members = WorkspaceMember.objects.filter(workspace=workspace).select_related("user")
        invitations = Invitation.objects.filter(workspace=workspace, accepted_at__isnull=True).order_by("-created_at")
        return Response({
            "members": [{**user_json(item.user), "role": item.role} for item in members],
            "invitations": [{"id": inv.id, "email": inv.email, "role": inv.role, "token": str(inv.token)} for inv in invitations],
        })

    current = WorkspaceMember.objects.filter(workspace=workspace, user=request.user).first()
    if not current or current.role not in ["owner", "admin"]:
        return Response({"detail": "Only workspace admins can invite members."}, status=403)
    email = (request.data.get("email") or "").strip().lower()
    if not email:
        return Response({"detail": "Email is required."}, status=400)
    role = request.data.get("role") if request.data.get("role") in ["admin", "member"] else "member"
    invite = Invitation.objects.filter(workspace=workspace, email__iexact=email, accepted_at__isnull=True).first()
    if not invite:
        invite = Invitation.objects.create(workspace=workspace, email=email, role=role, invited_by=request.user)
    invite_url = f"{request.build_absolute_uri('/').rstrip('/')}/?invite={invite.token}"
    try:
        send_mail(
            f"You're invited to {workspace.name}",
            f"You have been invited to join {workspace.name}. Open {invite_url}",
            None,
            [email],
            fail_silently=True,
        )
    except Exception:
        pass
    return Response({"id": invite.id, "email": invite.email, "role": invite.role, "invite_url": invite_url}, status=201)


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def accept_invitation_view(request, token):
    invite = Invitation.objects.filter(token=token, accepted_at__isnull=True).select_related("workspace").first()
    if not invite:
        return Response({"detail": "Invitation is invalid or already used."}, status=404)
    if request.method == "GET":
        return Response({"email": invite.email, "workspace": invite.workspace.name, "role": invite.role})
    password = request.data.get("password") or ""
    name = (request.data.get("name") or "").strip()
    if len(password) < 8:
        return Response({"detail": "Password must be at least 8 characters."}, status=400)
    user = User.objects.filter(username__iexact=invite.email).first()
    if not user:
        user = User.objects.create_user(username=invite.email, email=invite.email, password=password)
    else:
        user.set_password(password)
    if name:
        user.first_name = name
    user.email = invite.email
    user.save()
    WorkspaceMember.objects.get_or_create(workspace=invite.workspace, user=user, defaults={"role": invite.role})
    invite.accepted_at = timezone.now()
    invite.save(update_fields=["accepted_at"])
    token_obj, _ = Token.objects.get_or_create(user=user)
    return Response({"token": token_obj.key, "user": user_json(user)})
