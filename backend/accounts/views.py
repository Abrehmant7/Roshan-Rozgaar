"""Session-auth endpoints under /api/v1/auth/.

The POST views are plain Django JSON views wrapped in `csrf_protect`, so CSRF
is enforced even for anonymous login/registration requests (DRF's
SessionAuthentication only enforces it for already-authenticated users).
Error shape matches DRF: field errors as {"field": ["msg", ...]}, everything
else as {"detail": "msg"}.
"""

import json

from django.contrib.auth import authenticate, login, logout
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST
from rest_framework.response import Response
from rest_framework.views import APIView

from .forms import LoginForm, RegistrationForm
from .models import User
from .serializers import UserSerializer

REGISTRATION_FIELDS = {"username", "password"}
DUPLICATE_USERNAME = "A user with that username already exists."
INVALID_CREDENTIALS = "Invalid username or password."


def _error(detail, status=400):
    return JsonResponse({"detail": detail}, status=status)


def _json_body(request):
    """Return the request body as a dict, or None if it is not a JSON object."""
    try:
        data = json.loads(request.body or b"{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _non_string_fields(data, fields):
    return {
        name: ["Must be a string."]
        for name in fields
        if name in data and not isinstance(data[name], str)
    }


def _form_errors(form):
    return {field: [str(msg) for msg in msgs] for field, msgs in form.errors.items()}


@require_GET
@never_cache
def csrf_token_view(request):
    return JsonResponse({"csrf_token": get_token(request)})


@require_POST
@csrf_protect
@never_cache
def register_view(request):
    data = _json_body(request)
    if data is None:
        return _error("Request body must be a JSON object.")

    # Only username and password are accepted. Anything else (role, is_staff,
    # ...) is rejected outright rather than silently ignored.
    errors = {name: ["This field is not allowed."] for name in sorted(set(data) - REGISTRATION_FIELDS)}
    errors |= _non_string_fields(data, REGISTRATION_FIELDS)
    if errors:
        return JsonResponse(errors, status=400)

    form = RegistrationForm(data)
    if not form.is_valid():
        return JsonResponse(_form_errors(form), status=400)

    try:
        with transaction.atomic():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                password=form.cleaned_data["password"],
                role=User.Role.CUSTOMER,  # set by the server, never by the client
            )
    except IntegrityError:  # lost a race with a concurrent registration
        return JsonResponse({"username": [DUPLICATE_USERNAME]}, status=400)

    login(request, user)
    return JsonResponse(UserSerializer(user).data, status=201)


@require_POST
@csrf_protect
@never_cache
def login_view(request):
    data = _json_body(request)
    if data is None:
        return _error("Request body must be a JSON object.")
    if errors := _non_string_fields(data, ("username", "password")):
        return JsonResponse(errors, status=400)

    form = LoginForm(data)
    if not form.is_valid():
        return JsonResponse(_form_errors(form), status=400)

    user = authenticate(
        request,
        username=form.cleaned_data["username"],
        password=form.cleaned_data["password"],
    )
    if user is None:  # wrong username, wrong password, or inactive: same answer
        return _error(INVALID_CREDENTIALS)

    login(request, user)
    return JsonResponse(UserSerializer(user).data)


@require_POST
@csrf_protect
@never_cache
def logout_view(request):
    logout(request)
    return HttpResponse(status=204)


@method_decorator(never_cache, name="dispatch")
class MeView(APIView):
    """Uses the project defaults: SessionAuthentication + IsAuthenticated."""

    def get(self, request):
        return Response(UserSerializer(request.user).data)
