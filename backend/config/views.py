import logging

from django.db import connection
from django.http import JsonResponse
from django.views.csrf import csrf_failure as django_csrf_failure
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class HealthView(APIView):
    """Public liveness check that also confirms the database answers a query."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        except Exception:
            # Details go to the server log only, never to the client.
            logger.exception("Health check: database query failed")
            return Response(
                {"status": "unavailable", "database": "unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({"status": "ok", "database": "ok"})


def csrf_failure(request, reason=""):
    """JSON 403 for API clients; Django's normal HTML page everywhere else (e.g. Admin)."""
    if request.path.startswith("/api/"):
        return JsonResponse(
            {
                "detail": "CSRF verification failed. Fetch /api/v1/auth/csrf/ and send X-CSRFToken.",
                "code": "csrf_failed",
            },
            status=403,
        )
    return django_csrf_failure(request, reason=reason)
