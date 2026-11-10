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

    def test_registry_is_labelled_fictional(self):
        self.assertEqual(self.scan().json()["registry"], "fictional")

    def test_mock_without_keyword_picks_first_free_fictional_card(self):
        self.assertEqual(self.scan(name="photo.png").json()["identity"]["name_en"], "Imran Ali")  # card-5
        taken = make_user("taken_worker", role="worker")
        WorkerProfile.objects.create(
            user=taken, display_name="Taken", experience_years=1, verified_name="Imran Ali",
            id_masked="x", identity_digest=identity.identity_digest("0000000000055"), verified_at=timezone.now())
        self.assertEqual(self.scan(name="IMG_2041.jpg", content=b"\xff\xd8\xff" + b"\x00" * 20,
                                   ctype="image/jpeg").json()["identity"]["name_en"], "Tariq Javed")  # card-6

    def test_identity_already_linked_to_another_worker(self):
        proof = self.scan().json()["scan_proof"]
        self.assertEqual(self.api.put(ME, self.profile_body(proof)).status_code, 201)
        other = Session(make_user("other_worker", role="worker"))
        response = self.scan(api=other)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "identity_in_use")


FAKE_KEY = "sk-test-not-a-real-key"
LIVE = dict(OCR_MODE="live", OCR_ENDPOINT="https://pictotext.invalid/api/v1/ocr", OCR_API_KEY=FAKE_KEY,
            OCR_DOCUMENT_TYPE="pk_id_card", OCR_TIMEOUT_SECONDS=7)


def provider_ok(payload):
    fake = mock.MagicMock()
    fake.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    return fake


def provider_error(status, reason=None):
    body = {"error": {"code": status, "message": "provider message", "status": "ERR",
                      "details": [{"reason": reason}] if reason else []}}
    return error.HTTPError(LIVE["OCR_ENDPOINT"], status, "error", {}, BytesIO(json.dumps(body).encode()))


@override_settings(**LIVE)
class PicToTextAdapterTests(OnboardingBase):
    """The live adapter against PicToText's documented contract (network faked)."""

    def test_request_contract_and_id_number(self):
        payload = {"idNumber": "00000-0000003-3", "name": "RASHID MEHMOOD", "country": "PAKISTAN"}
        with mock.patch("workers.ocr.request.urlopen", return_value=provider_ok(payload)) as urlopen:
            response = self.scan()
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual((body["mode"], body["simulated"], body["registry"]), ("live", False, "fictional"))
        self.assertEqual(body["identity"]["name_en"], "Rashid Mehmood")
        sent = urlopen.call_args.args[0]
        self.assertEqual((sent.full_url, sent.get_method()), (LIVE["OCR_ENDPOINT"], "POST"))
        self.assertEqual(sent.get_header("Authorization"), f"Bearer {FAKE_KEY}")
        self.assertIn(b'name="documentType"\r\n\r\npk_id_card\r\n', sent.data)
        self.assertIn(b'name="image"; filename="card.png"\r\nContent-Type: image/png', sent.data)
        self.assertIn(PNG, sent.data)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 7)
        self.assertNotIn(FAKE_KEY, response.content.decode())

    def test_id_number_normalization(self):
        cases = {
            "00000 0000003 3": (201, None), "0000000000033": (201, None),
            "12345": (422, "id_not_found"), "": (422, "id_not_found"),
            "00000-0000099-9": (422, "id_not_registered"),
        }
        for raw, (status, code) in cases.items():
            with self.subTest(raw=raw), mock.patch("workers.ocr.request.urlopen",
                                                   return_value=provider_ok({"idNumber": raw})):
                response = self.scan()
                self.assertEqual(response.status_code, status)
                if code:
                    self.assertEqual(response.json()["code"], code)
        with mock.patch("workers.ocr.request.urlopen", return_value=provider_ok({"name": "NO NUMBER"})):
            self.assertEqual(self.scan().json()["code"], "id_not_found")

    def test_provider_errors_map_to_clear_codes(self):
        import socket

        cases = [
            (provider_error(401, "INVALID_API_KEY"), 503, "ocr_auth_rejected", False),
            (provider_error(403, "EMAIL_NOT_VERIFIED"), 503, "ocr_auth_rejected", False),
            (provider_error(402, "INSUFFICIENT_CREDITS"), 503, "ocr_quota_exceeded", False),
            (provider_error(429), 503, "ocr_quota_exceeded", True),
            (provider_error(400, "INVALID_IMAGE_TYPE"), 422, "image_rejected", True),
            (provider_error(400, "IMAGE_TOO_LARGE"), 422, "image_rejected", True),
            (provider_error(400, "INVALID_DOCUMENT_TYPE"), 503, "ocr_not_configured", False),
            (provider_error(500, "AI_SERVICE_ERROR"), 503, "ocr_unavailable", True),
            (TimeoutError(), 504, "ocr_timeout", True),
            (error.URLError(socket.timeout("timed out")), 504, "ocr_timeout", True),
            (error.URLError("name resolution failed"), 503, "ocr_unavailable", True),
        ]
        for exc, status, code, retryable in cases:
            with self.subTest(code=code, exc=repr(exc)[:40]),                     mock.patch("workers.ocr.request.urlopen", side_effect=exc),                     self.assertLogs("workers.views", "WARNING") as logs:
                response = self.scan()
                self.assertEqual(response.status_code, status)
                body = response.json()
                self.assertEqual((body["code"], body["retryable"]), (code, retryable))
                self.assertNotIn(FAKE_KEY, response.content.decode())
                self.assertNotIn(FAKE_KEY, " ".join(logs.output))
                self.assertIn(code, " ".join(logs.output))
        self.assertFalse(ScanProof.objects.exists())

    def test_non_json_answer_is_unavailable(self):
        fake = mock.MagicMock()
        fake.__enter__.return_value.read.return_value = b"<html>gateway</html>"
        with mock.patch("workers.ocr.request.urlopen", return_value=fake):
            self.assertEqual(self.scan().json()["code"], "ocr_unavailable")

    @override_settings(OCR_API_KEY="")
    def test_missing_key_is_reported_without_calling_the_provider(self):
        with mock.patch("workers.ocr.request.urlopen") as urlopen:
            response = self.scan()
        self.assertEqual(response.status_code, 503)
        self.assertEqual((response.json()["code"], response.json()["retryable"]), ("ocr_not_configured", False))
        urlopen.assert_not_called()

    def test_mock_mode_stays_selectable(self):
        with self.settings(OCR_MODE="mock"), mock.patch("workers.ocr.request.urlopen") as urlopen:
            body = self.scan().json()
        self.assertEqual((body["mode"], body["simulated"]), ("mock", True))
        urlopen.assert_not_called()


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
