from django.core.cache import cache
from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@extend_schema(exclude=True)
@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health(request):
    checks = {}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        checks["db"] = "ok"
    except Exception as exc:  # pragma: no cover - диагностика окружения
        checks["db"] = f"error: {exc}"
    try:
        cache.set("health", "1", 5)
        checks["cache"] = "ok" if cache.get("health") == "1" else "error"
    except Exception as exc:  # pragma: no cover
        checks["cache"] = f"error: {exc}"
    ok = all(v == "ok" for v in checks.values())
    return Response({"status": "ok" if ok else "degraded", "checks": checks}, status=200 if ok else 503)
