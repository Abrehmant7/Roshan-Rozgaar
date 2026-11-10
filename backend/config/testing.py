"""Test helpers shared by app test suites (not used at runtime)."""

import json

from django.test import Client

from accounts.models import User

PASSWORD = "Sabz-Chai-4821"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64  # header is all the mock OCR checks


class Session:
    """A CSRF-enforcing browser-like session following the React contract."""

    def __init__(self, user=None):
        self.client = Client(enforce_csrf_checks=True)
        self.token = None
        if user is not None:
            self.login(user)

    def refresh_csrf(self):
        self.token = self.client.get("/api/v1/auth/csrf/").json()["csrf_token"]

    def login(self, user, password=PASSWORD):
        self.refresh_csrf()
        response = self.client.post(
            "/api/v1/auth/login/",
            json.dumps({"username": user.username, "password": password}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token,
        )
        assert response.status_code == 200, response.content
        self.refresh_csrf()  # Django rotates the token on login
        return response

    def get(self, path, **params):
        return self.client.get(path, params)

    def _send(self, method, path, data=None, multipart=False, csrf=True):
        headers = {"HTTP_X_CSRFTOKEN": self.token} if csrf and self.token else {}
        send = getattr(self.client, method)
        if multipart:
            return send(path, data or {}, **headers)  # Django encodes multipart
        return send(path, json.dumps(data if data is not None else {}), content_type="application/json", **headers)

    def post(self, path, data=None, **kw):
        return self._send("post", path, data, **kw)

    def put(self, path, data=None, **kw):
        return self._send("put", path, data, **kw)

    def patch(self, path, data=None, **kw):
        return self._send("patch", path, data, **kw)


def make_user(username, role="customer", **extra):
    return User.objects.create_user(username, password=PASSWORD, role=role, **extra)


def make_worker(username, trades, areas, specialties=(), accepting=True, name=None, years=5):
    """A worker with a complete profile, bypassing the scan (tests only)."""
    import uuid

    from django.utils import timezone

    from workers.models import WorkerProfile

    user = make_user(username, role="worker")
    profile = WorkerProfile.objects.create(
        user=user, display_name=name or username.replace("_", " ").title(), experience_years=years,
        accepting_jobs=accepting, verified_name="Test Person", id_masked="*****-****000-0",
        identity_digest=uuid.uuid4().hex, identity_simulated=True, verified_at=timezone.now(),
    )
    profile.trades.set(trades)
    profile.service_areas.set(areas)
    profile.specialties.set(specialties)
    return user


WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 64  # Matroska/WebM magic + padding


def upload(name, content, content_type):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, content, content_type=content_type)
