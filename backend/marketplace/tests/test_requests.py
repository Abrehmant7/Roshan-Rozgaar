import os

from django.conf import settings
from django.test import override_settings

from config.testing import Session

from .base import BOARD, DISCOVER, JOBS, MarketplaceTestCase


class JobRequestCreateTests(MarketplaceTestCase):
    def test_typed_request_in_non_plumbing_trade(self):
        api = self.session(self.ayesha)
        response = self.post_job(api, specialty=self.wiring.id)
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertEqual(body["status"], "OPEN")
        self.assertEqual(body["trade"]["slug"], "electrical")
        self.assertEqual(body["trade"]["name_ur"], "بجلی کا کام")
        self.assertEqual(body["specialty"]["id"], self.wiring.id)
        self.assertEqual(body["service_area"]["sector_code"], "G-11")
        self.assertEqual(body["viewer"], "owner")
        self.assertEqual(body["address_details"], "House 12, Street 4")
        self.assertFalse(body["has_voice_note"])
        self.assertIsNone(body["voice_note_url"])
        self.assertRegex(body["created_at"], r"^\d{4}-\d\d-\d\dT")

    def test_voice_only_request_is_stored_privately_with_generated_name(self):
        api = self.session(self.ayesha)
        response = self.post_job(api, description="", address_details="",
                                 voice=("my secret name.webm", self.WEBM, "audio/webm"))
        self.assertEqual(response.status_code, 201, response.content)
        body = response.json()
        self.assertTrue(body["has_voice_note"])
        self.assertEqual(body["voice_note_url"], f"/api/v1/job-requests/{body['id']}/voice-note/")
        stored = os.listdir(os.path.join(settings.PRIVATE_MEDIA_ROOT, "voice-notes"))
        self.assertEqual(len(stored), 1)
        self.assertRegex(stored[0], r"^[0-9a-f]{32}\.webm$")

    def test_validation(self):
        api = self.session(self.ayesha)
        cases = {
            "specialty from another trade": ({"specialty": self.leak.id}, "specialty"),
            "nothing to describe the job": ({"description": "   "}, "description"),
            "unknown area": ({"service_area": 999999}, "service_area"),
            "missing trade": ({"trade": None}, "trade"),
        }
        for label, (override, field) in cases.items():
            with self.subTest(label):
                response = self.post_job(api, **override)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
        bad_audio = self.post_job(api, voice=("note.txt", b"hello world, not audio", "audio/webm"))
        self.assertEqual(bad_audio.status_code, 400)
        self.assertIn("voice_note", bad_audio.json())
        with override_settings(VOICE_NOTE_MAX_BYTES=16):
            self.assertIn("voice_note", self.post_job(api, voice=self.WEBM).json())
        self.carpentry.is_active = False
        self.carpentry.save()
        self.assertIn("trade", self.post_job(api, trade=self.carpentry.id).json())

    def test_only_customers_post_and_list(self):
        worker = self.session(self.akram)
        self.assertEqual(self.post_job(worker).json()["code"], "customer_role_required")
        self.assertEqual(worker.get(JOBS).status_code, 403)
        anon = Session()
        anon.refresh_csrf()
        self.assertEqual(self.post_job(anon).status_code, 403)
        no_csrf = self.session(self.ayesha).post(JOBS, {"trade": self.electrical.id}, csrf=False)
        self.assertEqual(no_csrf.status_code, 403)

    def test_customer_lists_only_own_requests(self):
        ayesha, bilal = self.session(self.ayesha), self.session(self.bilal)
        mine = self.post_job(ayesha).json()["id"]
        self.post_job(bilal)
        listing = ayesha.get(JOBS).json()
        self.assertEqual(listing["count"], 1)
        self.assertEqual([r["id"] for r in listing["results"]], [mine])


class BoardAndAccessTests(MarketplaceTestCase):
    def setUp(self):
        self.owner = self.session(self.ayesha)
        self.job = self.post_job(self.owner, description="Fan wiring", voice=self.WEBM).json()
        self.detail = f"{JOBS}{self.job['id']}/"
        self.audio = f"{JOBS}{self.job['id']}/voice-note/"

    def test_only_matching_workers_see_it_on_the_board(self):
        for worker, visible in ((self.akram, True), (self.naveed, True), (self.rashid, False), (self.sajid, False)):
            with self.subTest(worker=worker.username):
                ids = [r["id"] for r in self.session(worker).get(BOARD).json()["results"]]
                self.assertEqual(self.job["id"] in ids, visible)
        item = self.session(self.akram).get(BOARD).json()["results"][0]
        self.assertNotIn("address_details", item)
        self.assertNotIn("customer", item)
        self.assertEqual(item["viewer"], "eligible_worker")

    def test_board_requires_onboarded_worker(self):
        self.assertEqual(self.session(self.newbie).get(BOARD).json()["code"], "profile_incomplete")
        self.assertEqual(self.owner.get(BOARD).json()["code"], "worker_role_required")

    def test_detail_access(self):
        self.assertIn("address_details", self.owner.get(self.detail).json())
        eligible = self.session(self.akram).get(self.detail)
        self.assertEqual(eligible.status_code, 200)
        self.assertNotIn("address_details", eligible.json())
        for user in (self.sajid, self.rashid, self.bilal, self.newbie):
            with self.subTest(user=user.username):
                self.assertEqual(self.session(user).get(self.detail).status_code, 404)

    def test_voice_note_playback_permissions(self):
        for user in (self.ayesha, self.akram, self.naveed):
            with self.subTest(user=user.username):
                response = self.session(user).get(self.audio)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "audio/webm")
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assertEqual(b"".join(response.streaming_content), self.WEBM)
        for user in (self.sajid, self.rashid, self.bilal):
            with self.subTest(user=user.username):
                self.assertEqual(self.session(user).get(self.audio).status_code, 404)
        anon = Session()
        self.assertEqual(anon.get(self.audio).status_code, 403)

    def test_missing_voice_media_is_handled(self):
        typed = self.post_job(self.owner).json()
        response = self.owner.get(f"{JOBS}{typed['id']}/voice-note/")
        self.assertEqual(response.json()["code"], "voice_note_missing")
        for name in os.listdir(os.path.join(settings.PRIVATE_MEDIA_ROOT, "voice-notes")):
            os.remove(os.path.join(settings.PRIVATE_MEDIA_ROOT, "voice-notes", name))
        self.assertEqual(self.owner.get(self.audio).json()["code"], "voice_note_missing")

    def test_board_follows_profile_changes(self):
        akram = self.session(self.akram)
        self.assertEqual(akram.get(BOARD).json()["count"], 1)
        self.akram.worker_profile.service_areas.set([self.i10])
        self.assertEqual(akram.get(BOARD).json()["count"], 0)
        self.assertEqual(akram.get(self.detail).status_code, 404)


class DiscoveryTests(MarketplaceTestCase):
    def find(self, user=None, **params):
        return self.session(user or self.ayesha).get(DISCOVER, **params)

    def test_filters_and_specialty_ranking(self):
        body = self.find(trade=self.electrical.id, service_area=self.g11.id, specialty=self.wiring.id).json()
        names = [w["display_name"] for w in body["results"]]
        self.assertEqual(names, ["Akram", "Naveed"])  # specialist first, generalist included
        first = body["results"][0]
        self.assertTrue(first["matches_specialty"])
        self.assertFalse(body["results"][1]["matches_specialty"])
        self.assertEqual(first["rating"], {"average": None, "count": 0})
        self.assertEqual(first["completed_jobs"], 0)
        self.assertTrue(first["is_available"])
        self.assertNotIn("id_masked", first)

        g13 = self.find(trade=self.electrical.id, service_area=self.g13.id).json()
        self.assertEqual([w["display_name"] for w in g13["results"]], ["Naveed"])
        plumbing = self.find(trade=self.plumbing.id, service_area=self.g11.id).json()
        self.assertEqual([w["display_name"] for w in plumbing["results"]], ["Sajid"])

    def test_excludes_workers_not_accepting_jobs_or_incomplete(self):
        self.naveed.worker_profile.accepting_jobs = False
        self.naveed.worker_profile.save()
        names = [w["display_name"] for w in self.find(trade=self.electrical.id, service_area=self.g11.id).json()["results"]]
        self.assertEqual(names, ["Akram"])
        self.g11.is_active = False
        self.g11.save()
        self.assertIn("service_area", self.find(trade=self.electrical.id, service_area=self.g11.id).json())

    def test_query_validation_and_auth(self):
        self.assertIn("trade", self.find(service_area=self.g11.id).json())
        bad = self.find(trade=self.electrical.id, service_area=self.g11.id, specialty=self.leak.id)
        self.assertIn("specialty", bad.json())
        self.assertEqual(Session().get(DISCOVER, trade=self.electrical.id, service_area=self.g11.id).status_code, 403)
        empty = self.find(trade=self.carpentry.id, service_area=self.g11.id).json()
        self.assertEqual(empty, {"count": 0, "next": None, "previous": None, "results": []})
