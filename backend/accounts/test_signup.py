"""Worker self-signup, username normalization and case-insensitive uniqueness."""

import importlib
import json
import threading

from django.apps import apps as django_apps
from django.db import IntegrityError, connection, transaction
from django.test import Client, TestCase, TransactionTestCase

from config.testing import PASSWORD, Session

from .models import User

WORKER_SIGNUP = "/api/v1/auth/register/worker/"
CUSTOMER_SIGNUP = "/api/v1/auth/register/"


class WorkerSignupTests(TestCase):
    def setUp(self):
        self.api = Session()
        self.api.refresh_csrf()

    def signup(self, path=WORKER_SIGNUP, **body):
        return self.api.post(path, {"username": "ustad_new", "password": PASSWORD, **body})

    def test_creates_worker_session_without_privileges(self):
        response = self.signup()
        self.assertEqual(response.status_code, 201, response.content)
        user = User.objects.get(username="ustad_new")
        self.assertEqual(response.json(), {"id": user.id, "username": "ustad_new", "role": "worker"})
        self.assertFalse(user.is_staff or user.is_superuser)
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(self.api.get("/api/v1/auth/me/").json()["role"], "worker")
        # The account exists, but there is no profile until the ID scan + profile step.
        self.assertEqual(self.api.get("/api/v1/workers/me/").json()["code"], "profile_not_found")
        self.assertEqual(self.api.get("/api/v1/workers/me/dashboard/").json()["profile_status"], "missing")
        self.assertEqual(self.api.get("/api/v1/job-board/").json()["code"], "profile_incomplete")

    def test_role_and_staff_cannot_be_chosen_by_the_client(self):
        for extra in ({"role": "customer"}, {"is_staff": True}, {"is_superuser": True}):
            with self.subTest(extra=extra):
                response = self.signup(**extra)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()[next(iter(extra))], ["This field is not allowed."])
        self.assertFalse(User.objects.exists())

    def test_requires_csrf(self):
        response = self.api.post(WORKER_SIGNUP, {"username": "ustad_new", "password": PASSWORD}, csrf=False)
        self.assertEqual((response.status_code, response.json()["code"]), (403, "csrf_failed"))
        self.assertEqual(Client().get(WORKER_SIGNUP).status_code, 405)

    def test_same_validation_as_customer_signup(self):
        self.assertIn("password", self.signup(password="12345678").json())
        self.assertIn("username", self.signup(username="has space").json())
        User.objects.create_user("Taken_Name", password=PASSWORD)
        self.assertEqual(self.signup(username="taken_name").json(),
                         {"username": ["A user with that username already exists."]})

    def test_customer_signup_unchanged(self):
        response = self.signup(path=CUSTOMER_SIGNUP, username="ayesha_new")
        self.assertEqual((response.status_code, response.json()["role"]), (201, "customer"))


class UsernameNormalizationTests(TestCase):
    def setUp(self):
        self.api = Session()
        self.api.refresh_csrf()

    def register(self, username):
        return self.api.post(CUSTOMER_SIGNUP, {"username": username, "password": PASSWORD})

    def test_length_is_checked_after_nfkc_normalization(self):
        # U+FB01 "fi" ligature: 1 character that NFKC turns into 2.
        too_long = "ﬁ" * 76  # 76 raw characters, 152 once normalized
        response = self.register(too_long)
        self.assertEqual(response.status_code, 400)  # previously passed the form and hit the DB column
        self.assertIn("username", response.json())
        self.assertFalse(User.objects.exists())

        fits = "ﬁ" * 75  # 150 once normalized
        response = self.register(fits)
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(User.objects.get().username, "fi" * 75)

    def test_database_rejects_case_variants(self):
        User.objects.create_user("Racer", password=PASSWORD)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("rACER", password=PASSWORD)

    def test_migration_reports_existing_collisions_without_deleting(self):
        migration = importlib.import_module("accounts.migrations.0003_username_case_insensitive_unique")
        constraint = next(c for c in User._meta.constraints if c.name == "accounts_user_username_ci_unique")
        with connection.schema_editor() as editor:
            editor.remove_constraint(User, constraint)  # simulate a database from before the fix
        User.objects.create_user("Bilal", password=PASSWORD)
        User.objects.create_user("bilal", password=PASSWORD)
        User.objects.create_user("unique_one", password=PASSWORD)
        with self.assertRaises(RuntimeError) as ctx:
            migration.refuse_if_case_collisions(django_apps, None)
        self.assertIn("Bilal, bilal", str(ctx.exception))
        self.assertIn("No accounts were changed", str(ctx.exception))
        self.assertEqual(User.objects.count(), 3)


class ConcurrentSignupTests(TransactionTestCase):
    def test_case_variants_racing_produce_one_account(self):
        barrier = threading.Barrier(2)
        statuses = []

        def signup(name):
            client = Client(enforce_csrf_checks=True)
            token = client.get("/api/v1/auth/csrf/").json()["csrf_token"]
            barrier.wait()
            try:
                response = client.post(CUSTOMER_SIGNUP, json.dumps({"username": name, "password": PASSWORD}),
                                       content_type="application/json", HTTP_X_CSRFTOKEN=token)
                statuses.append(response.status_code)
            finally:
                connection.close()

        threads = [threading.Thread(target=signup, args=(n,)) for n in ("Zara_K", "ZARA_k")]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        self.assertEqual(sorted(statuses), [201, 400])
        self.assertEqual(User.objects.filter(username__iexact="zara_k").count(), 1)
