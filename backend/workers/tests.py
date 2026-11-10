import json
from datetime import timedelta
from io import BytesIO, StringIO
from unittest import mock
from urllib import error

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from catalog.models import ServiceArea, Specialty, Trade
from config.testing import PNG, Session, make_user, upload

from . import identity
from .models import ScanProof, WorkerProfile

SCAN = "/api/v1/workers/me/scan/"
ME = "/api/v1/workers/me/"
AVAILABILITY = "/api/v1/workers/me/availability/"


class OnboardingBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=StringIO())
        cls.electrical = Trade.objects.get(slug="electrical")
        cls.plumbing = Trade.objects.get(slug="plumbing")
        cls.wiring = Specialty.objects.get(trade=cls.electrical, slug="wiring")
        cls.leak = Specialty.objects.get(trade=cls.plumbing, slug="leak-repair")
        cls.g11 = ServiceArea.objects.get(sector_code="G-11")
        cls.i10 = ServiceArea.objects.get(sector_code="I-10")

    def setUp(self):
        self.worker = make_user("ustad_imran", role="worker")
        self.api = Session(self.worker)

    def scan(self, name="card-5.png", content=PNG, ctype="image/png", api=None):
        return (api or self.api).post(SCAN, {"image": upload(name, content, ctype)}, multipart=True)

    def profile_body(self, proof=None, **overrides):
        body = {
            "display_name": "Imran Electrician",
            "experience_years": 12,
            "trades": [self.electrical.id],
            "specialties": [self.wiring.id],
            "service_areas": [self.g11.id, self.i10.id],
        }
        if proof:
            body["scan_proof"] = proof
        body.update(overrides)
        return body


class ScanTests(OnboardingBase):
    def test_mock_scan_returns_masked_identity_and_proof(self):
        response = self.scan()
        self.assertEqual(response.status_code, 201)
        body = response.json()
        self.assertEqual(body["mode"], "mock")
        self.assertTrue(body["simulated"])
        self.assertEqual(body["identity"], {"name_en": "Imran Ali", "name_ur": "عمران علی", "id_masked": "*****-****005-5"})
        self.assertTrue(body["scan_proof"])
        self.assertNotIn("0000000000055", response.content.decode())
        self.assertNotIn("00000-0000005-5", response.content.decode())
        proof = ScanProof.objects.get(user=self.worker)
        self.assertNotEqual(proof.token_hash, body["scan_proof"])  # only a hash is stored

    def test_scan_requires_worker_session_and_csrf(self):
        anon = Session()
        anon.refresh_csrf()
        self.assertEqual(self.scan(api=anon).json()["code"], "not_authenticated")
        customer = Session(make_user("ayesha"))
        response = self.scan(api=customer)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "worker_role_required")
        no_csrf = self.api.post(SCAN, {"image": upload("card-5.png", PNG, "image/png")}, multipart=True, csrf=False)
        self.assertEqual(no_csrf.status_code, 403)

    def test_image_validation(self):
        self.assertIn("image", self.api.post(SCAN, {}, multipart=True).json())
        bad = self.scan(name="card.gif", content=b"GIF89a" + b"\x00" * 20, ctype="image/gif")
        self.assertEqual(bad.status_code, 400)
        self.assertIn("image", bad.json())
        with self.settings(OCR_MAX_IMAGE_BYTES=32):
            self.assertEqual(self.scan().status_code, 400)

    def test_mock_failure_paths(self):
        cases = {
            "blurry.jpg": (422, "id_not_found"),
            "unregistered.jpg": (422, "id_not_registered"),
            "ocr-error.jpg": (503, "ocr_unavailable"),
        }
        for name, (status, code) in cases.items():
            with self.subTest(name=name):
                response = self.scan(name=name, content=b"\xff\xd8\xff" + b"\x00" * 20, ctype="image/jpeg")
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["code"], code)
                self.assertTrue(response.json()["retryable"])
        self.assertFalse(ScanProof.objects.exists())

    def test_identity_already_linked_to_another_worker(self):
        proof = self.scan().json()["scan_proof"]
        self.assertEqual(self.api.put(ME, self.profile_body(proof)).status_code, 201)
        other = Session(make_user("other_worker", role="worker"))
        response = self.scan(api=other)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "identity_in_use")


@override_settings(OCR_MODE="live", OCR_ENDPOINT="https://ocr.invalid/v1/read", OCR_API_KEY="test-key",
                   OCR_TEXT_FIELD="result.text")
class LiveAdapterTests(OnboardingBase):
    def test_live_success_sends_key_server_side(self):
        payload = json.dumps({"result": {"text": "NAME\nIDENTITY NUMBER 00000-0000003-3"}}).encode()
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = payload
        with mock.patch("workers.ocr.request.urlopen", return_value=fake) as urlopen:
            response = self.scan()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["mode"], "live")
        self.assertFalse(response.json()["simulated"])
        self.assertEqual(response.json()["identity"]["name_en"], "Rashid Mehmood")
        sent = urlopen.call_args.args[0]
        self.assertEqual(sent.get_header("X-api-key"), "test-key")
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 10)
        self.assertNotIn("test-key", response.content.decode())

    def test_live_provider_failure_is_retryable_503(self):
        for exc in (error.URLError("down"), TimeoutError()):
            with self.subTest(exc=type(exc).__name__), mock.patch("workers.ocr.request.urlopen", side_effect=exc):
                response = self.scan()
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {
                    "detail": "Could not read the card right now. Please try again.",
                    "code": "ocr_unavailable", "retryable": True})

    def test_live_unexpected_shape_is_503(self):
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = b'{"other": 1}'
        with mock.patch("workers.ocr.request.urlopen", return_value=fake):
            self.assertEqual(self.scan().status_code, 503)


class ProfileTests(OnboardingBase):
    def test_full_onboarding_in_non_plumbing_trade(self):
        self.assertEqual(self.api.get(ME).json()["code"], "profile_not_found")
        proof = self.scan().json()["scan_proof"]
        response = self.api.put(ME, self.profile_body(proof))
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["trades"], [self.electrical.id])
        self.assertEqual(body["specialties"], [self.wiring.id])
        self.assertEqual(body["service_areas"], sorted([self.g11.id, self.i10.id]))
        self.assertTrue(body["is_complete"])
        self.assertTrue(body["is_available"])
        self.assertTrue(body["accepting_jobs"])
        self.assertEqual(body["verification"]["name"], "Imran Ali")
        self.assertTrue(body["verification"]["simulated"])
        self.assertEqual(self.api.get(ME).json(), body)
        profile = WorkerProfile.objects.get(user=self.worker)
        self.assertEqual(profile.identity_digest, identity.identity_digest("0000000000055"))

    def test_new_profile_requires_scan_proof(self):
        response = self.api.put(ME, self.profile_body())
        self.assertEqual(response.status_code, 400)
        self.assertIn("scan_proof", response.json())

    def test_proof_replay_expiry_and_ownership(self):
        proof = self.scan().json()["scan_proof"]
        self.assertEqual(self.api.put(ME, self.profile_body(proof)).status_code, 201)
        WorkerProfile.objects.filter(user=self.worker).delete()
        replay = self.api.put(ME, self.profile_body(proof))
        self.assertEqual(replay.status_code, 400)
        self.assertIn("already used", replay.json()["scan_proof"][0])

        proof = self.scan(name="card-6.png").json()["scan_proof"]
        ScanProof.objects.filter(used_at__isnull=True).update(expires_at=timezone.now() - timedelta(seconds=1))
        expired = self.api.put(ME, self.profile_body(proof))
        self.assertIn("expired", expired.json()["scan_proof"][0])

        proof = self.scan(name="card-6.png").json()["scan_proof"]
        thief = Session(make_user("thief", role="worker"))
        stolen = thief.put(ME, self.profile_body(proof))
        self.assertIn("not valid", stolen.json()["scan_proof"][0])
        self.assertFalse(WorkerProfile.objects.exists())

    def test_invalid_catalog_combinations(self):
        proof = self.scan().json()["scan_proof"]
        cases = {
            "specialty of unselected trade": ({"specialties": [self.leak.id]}, "specialties"),
            "no trades": ({"trades": []}, "trades"),
            "no areas": ({"service_areas": []}, "service_areas"),
            "unknown trade": ({"trades": [999999]}, "trades"),
            "experience out of range": ({"experience_years": 99}, "experience_years"),
        }
        for label, (override, field) in cases.items():
            with self.subTest(label):
                response = self.api.put(ME, self.profile_body(proof, **override))
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        Trade.objects.filter(pk=self.plumbing.pk).update(is_active=False)
        response = self.api.put(ME, self.profile_body(proof, trades=[self.plumbing.id], specialties=[]))
        self.assertIn("trades", response.json())
        # proof was not consumed by failed attempts
        self.assertEqual(self.api.put(ME, self.profile_body(proof)).status_code, 201)

    def test_edit_without_new_proof_and_availability_toggle(self):
        proof = self.scan().json()["scan_proof"]
        self.api.put(ME, self.profile_body(proof))
        response = self.api.put(ME, self.profile_body(display_name="Imran Bijli Wala", specialties=[]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["display_name"], "Imran Bijli Wala")
        self.assertEqual(response.json()["specialties"], [])

        off = self.api.patch(AVAILABILITY, {"accepting_jobs": False})
        self.assertEqual(off.json(), {"accepting_jobs": False, "is_available": False})
        self.assertFalse(self.api.get(ME).json()["is_available"])
        self.assertTrue(self.api.get(ME).json()["is_complete"])
        self.assertEqual(self.api.patch(AVAILABILITY, {"accepting_jobs": True}).json()["is_available"], True)
        self.assertIn("accepting_jobs", self.api.patch(AVAILABILITY, {}).json())

    def test_retired_trade_makes_profile_incomplete(self):
        proof = self.scan().json()["scan_proof"]
        self.api.put(ME, self.profile_body(proof))
        Trade.objects.filter(pk=self.electrical.pk).update(is_active=False)
        body = self.api.get(ME).json()
        self.assertFalse(body["is_complete"])
        self.assertFalse(body["is_available"])

    def test_availability_without_profile(self):
        self.assertEqual(self.api.patch(AVAILABILITY, {"accepting_jobs": True}).status_code, 404)
