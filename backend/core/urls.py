from django.urls import path
from .views import health
from .api import (
    accept_invitation_view,
    dashboard_view,
    login_view,
    me_view,
    members_view,
    project_detail_view,
    projects_view,
    task_detail_view,
    tasks_view,
)

urlpatterns = [
    path("health/", health, name="health"),
    path("auth/login/", login_view, name="login"),
    path("auth/me/", me_view, name="me"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("projects/", projects_view, name="projects"),
    path("projects/<int:project_id>/", project_detail_view, name="project-detail"),
    path("tasks/", tasks_view, name="tasks"),
    path("tasks/<int:task_id>/", task_detail_view, name="task-detail"),
    path("members/", members_view, name="members"),
    path("invitations/<uuid:token>/", accept_invitation_view, name="accept-invitation"),
]
