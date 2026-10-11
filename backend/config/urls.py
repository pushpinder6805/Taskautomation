from django.contrib import admin
from django.urls import include, path, re_path
from core.views import frontend

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    re_path(r"^(?!api/|admin/).*$", frontend, name="frontend"),
]
