"""Shared DRF building blocks: error shape, role permissions, pagination.

Error contract (all API apps):
- field validation errors: {"field": ["message", ...]}            (HTTP 400)
- everything else:         {"detail": "message", "code": "stable_code", ...extra}
  e.g. 403 not_authenticated / permission_denied / worker_role_required,
       404 not_found, 409 conflicts, 422 unreadable input, 503 provider down.
"""

from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import BasePermission
from rest_framework.views import exception_handler as drf_exception_handler


class ApiError(APIException):
    """APIException with a stable code and optional extra top-level fields."""

    def __init__(self, detail, code, status_code=status.HTTP_400_BAD_REQUEST, **extra):
        self.status_code = status_code
        self.extra = extra
        super().__init__(detail=detail, code=code)


def conflict(detail, code, **extra):
    return ApiError(detail, code, status.HTTP_409_CONFLICT, **extra)


def exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if isinstance(data, dict) and set(data) == {"detail"} and hasattr(data["detail"], "code"):
        data["code"] = data["detail"].code
    if isinstance(data, dict) and getattr(exc, "extra", None):
        data.update(exc.extra)
    return response


class _RolePermission(BasePermission):
    role = None

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == self.role)


class IsCustomer(_RolePermission):
    role = "customer"
    message = "This action needs a customer account."
    code = "customer_role_required"


class IsWorker(_RolePermission):
    role = "worker"
    message = "This action needs a worker account."
    code = "worker_role_required"


class StandardPagination(PageNumberPagination):
    """{"count", "next", "previous", "results"}; ?page=N&page_size=M (max 50)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 50
