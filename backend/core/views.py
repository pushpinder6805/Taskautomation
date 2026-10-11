from pathlib import Path
from django.conf import settings
from django.http import FileResponse, JsonResponse


def health(request):
    return JsonResponse({"status": "ok"})


def frontend(request):
    index = Path(settings.FRONTEND_DIST) / "index.html"
    if index.exists():
        return FileResponse(index.open("rb"), content_type="text/html")
    return JsonResponse({"detail": "Frontend build not found."}, status=503)
