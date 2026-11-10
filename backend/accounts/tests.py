from django.test import Client, TestCase

from .models import User

PASSWORD = "Sabz-Chai-4821"


class AuthClient:
    """Wraps a CSRF-enforcing test client and follows the documented React sequence."""

    def __init__(self):
        self.client = Client(enforce_csrf_checks=True)
        self.token = None

    def refresh_csrf(self):
        response = self.client.get("/api/v1/auth/csrf/")
        assert response.status_code == 200
        self.token = response.json()["csrf_token"]
        return response

    def post(self, path, data=None, token=True):
        headers = {"HTTP_X_CSRFTOKEN": self.token} if token and self.token else {}
        return self.client.post(path, data or {}, content_type="application/json", **headers)

    def me(self):
        return self.client.get("/api/v1/auth/me/")


class CsrfEndpointTests(TestCase):
    def test_returns_token_sets_cookie_and_disables_caching(self):
        response = AuthClient().refresh_csrf()
        self.assertTrue(response.json()["csrf_token"])
        self.assertIn("csrftoken", response.cookies)
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertIn("no-store", response["Cache-Control"])


class LoginFlowTests(TestCase):
    def setUp(self):
        self.worker = User.objects.create_user("ustad_akram", password=PASSWORD, role=User.Role.WORKER)
        self.customer = User.objects.create_user("ayesha", password=PASSWORD)

    def test_login_without_csrf_token_is_rejected(self):
        api = AuthClient()
        response = api.post("/api/v1/auth/login/", {"username": "ayesha", "password": PASSWORD}, token=False)
        self.assertEqual(response.status_code, 403)
        self.assertIn("CSRF", response.json()["detail"])
        self.assertEqual(api.me().status_code, 403)

    def test_login_with_cookie_but_no_header_is_rejected(self):
        api = AuthClient()
        api.refresh_csrf()
        response = api.post("/api/v1/auth/login/", {"username": "ayesha", "password": PASSWORD}, token=False)
        self.assertEqual(response.status_code, 403)

    def test_full_session_lifecycle_for_both_roles(self):
        for user in (self.worker, self.customer):
            with self.subTest(role=user.role):
                api = AuthClient()
                api.refresh_csrf()
                response = api.post("/api/v1/auth/login/", {"username": user.username, "password": PASSWORD})
                self.assertEqual(response.status_code, 200)
                expected = {"id": user.id, "username": user.username, "role": user.role}
                self.assertEqual(response.json(), expected)
                self.assertIn("sessionid", api.client.cookies)
                self.assertTrue(api.client.cookies["sessionid"]["httponly"])

                me = api.me()
                self.assertEqual(me.status_code, 200)
                self.assertEqual(me.json(), expected)

                # Django rotates the token on login; the pre-login token is now stale.
                stale = api.token
                api.refresh_csrf()
                self.assertNotEqual(stale, api.token)

                self.assertEqual(api.post("/api/v1/auth/logout/").status_code, 204)
                self.assertEqual(api.me().status_code, 403)

    def test_logout_requires_csrf(self):
        api = AuthClient()
        api.refresh_csrf()
        api.post("/api/v1/auth/login/", {"username": "ayesha", "password": PASSWORD})
        api.refresh_csrf()
        self.assertEqual(api.post("/api/v1/auth/logout/", token=False).status_code, 403)
        self.assertEqual(api.me().status_code, 200)

    def test_invalid_credentials_get_one_generic_error(self):
        api = AuthClient()
        api.refresh_csrf()
        self.worker.is_active = False
        self.worker.save()
        attempts = [
            {"username": "ayesha", "password": "wrong-password"},
            {"username": "nobody", "password": PASSWORD},
            {"username": "ustad_akram", "password": PASSWORD},  # inactive account
        ]
        bodies = []
        for payload in attempts:
            response = api.post("/api/v1/auth/login/", payload)
            self.assertEqual(response.status_code, 400)
            bodies.append(response.json())
        self.assertEqual(bodies, [{"detail": "Invalid username or password.", "code": "invalid_credentials"}] * 3)

    def test_login_requires_both_fields(self):
        api = AuthClient()
        api.refresh_csrf()
        response = api.post("/api/v1/auth/login/", {"username": "ayesha"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_auth_post_endpoints_reject_get(self):
        client = Client()
        for path in ("register", "login", "logout"):
            self.assertEqual(client.get(f"/api/v1/auth/{path}/").status_code, 405)


class RegistrationTests(TestCase):
    def setUp(self):
        self.api = AuthClient()
        self.api.refresh_csrf()

    def register(self, payload, token=True):
        return self.api.post("/api/v1/auth/register/", payload, token=token)

    def test_register_creates_customer_and_signs_in(self):
        response = self.register({"username": "bilal", "password": PASSWORD})
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="bilal")
        self.assertEqual(response.json(), {"id": user.id, "username": "bilal", "role": "customer"})
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)  # hashed by create_user()
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertEqual(self.api.me().json()["role"], "customer")

    def test_register_without_csrf_token_is_rejected(self):
        response = self.register({"username": "bilal", "password": PASSWORD}, token=False)
        self.assertEqual(response.status_code, 403)
        self.assertFalse(User.objects.filter(username="bilal").exists())

    def test_payload_cannot_grant_worker_or_staff(self):
        for extra in (
            {"role": "worker"},
            {"is_staff": True},
            {"is_superuser": True},
            {"role": "worker", "is_staff": True, "is_superuser": True, "groups": [1]},
        ):
            with self.subTest(extra=extra):
                response = self.register({"username": "sneaky", "password": PASSWORD, **extra})
                self.assertEqual(response.status_code, 400)
                for field in extra:
                    self.assertEqual(response.json()[field], ["This field is not allowed."])
                self.assertFalse(User.objects.filter(username="sneaky").exists())
        self.assertFalse(User.objects.filter(is_staff=True).exists())
        self.assertFalse(User.objects.filter(role=User.Role.WORKER).exists())

    def test_duplicate_username_is_a_field_error(self):
        User.objects.create_user("bilal", password=PASSWORD)
        response = self.register({"username": "Bilal", "password": PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"username": ["A user with that username already exists."]})

    def test_django_password_validators_apply(self):
        response = self.register({"username": "bilal", "password": "12345678"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("password", response.json())

    def test_django_username_validator_applies(self):
        response = self.register({"username": "has space", "password": PASSWORD})
        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json())

    def test_non_string_and_non_object_payloads(self):
        self.assertEqual(self.register({"username": ["x"], "password": PASSWORD}).json(),
                         {"username": ["Must be a string."]})
        response = self.api.client.post("/api/v1/auth/register/", "[1, 2]", content_type="application/json",
                                        HTTP_X_CSRFTOKEN=self.api.token)
        self.assertEqual(response.status_code, 400)


class AdminRoleTests(TestCase):
    def test_role_is_on_admin_add_and_change_forms(self):
        admin_user = User.objects.create_superuser("root", password=PASSWORD)
        client = Client()
        client.force_login(admin_user)
        self.assertContains(client.get("/admin/accounts/user/add/"), 'name="role"')
        self.assertContains(client.get(f"/admin/accounts/user/{admin_user.pk}/change/"), 'name="role"')

        response = client.post("/admin/accounts/user/add/", {
            "username": "ustad_naveed", "usable_password": "true",
            "password1": PASSWORD, "password2": PASSWORD, "role": "worker",
        })
        self.assertEqual(response.status_code, 302)
        worker = User.objects.get(username="ustad_naveed")
        self.assertEqual(worker.role, User.Role.WORKER)
        self.assertFalse(worker.is_staff)  # role and staff flags are independent
