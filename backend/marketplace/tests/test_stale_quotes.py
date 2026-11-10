"""Quote acceptance rechecks the worker's current trade and service-area coverage."""

from config.testing import PNG, PASSWORD, Session, upload

from ..models import Booking
from .base import DISCOVER, JOBS, MarketplaceTestCase


class StaleQuoteTests(MarketplaceTestCase):
    def setUp(self):
        self.owner = self.session(self.ayesha)
        self.sajid_api = self.session(self.sajid)  # plumber in G-11
        self.job = self.post_job(self.owner, trade=self.plumbing.id, specialty=self.leak.id,
                                 description="Tap leaking").json()
        self.quote = self.sajid_api.post(f"{JOBS}{self.job['id']}/quotes/", {"amount": "1200"}).json()
        self.accept_url = f"/api/v1/quotes/{self.quote['id']}/accept/"

    def test_worker_dropped_the_trade_after_quoting(self):
        self.sajid.worker_profile.trades.set([self.electrical])  # no longer offers plumbing
        quotes = self.owner.get(f"{JOBS}{self.job['id']}/quotes/").json()
        self.assertFalse(quotes[0]["worker_eligible"])
        self.assertFalse(self.owner.get(f"{JOBS}{self.job['id']}/").json()["quotes"][0]["worker_eligible"])
        response = self.owner.post(self.accept_url)
        self.assertEqual((response.status_code, response.json()["code"]), (409, "worker_not_eligible"))
        self.assertFalse(Booking.objects.exists())

    def test_worker_dropped_the_area_after_quoting(self):
        self.sajid.worker_profile.service_areas.set([self.i10])
        self.assertEqual(self.owner.post(self.accept_url).json()["code"], "worker_not_eligible")

    def test_retired_trade_blocks_acceptance(self):
        # Worker keeps another active trade (still available) but the job's trade is retired.
        self.sajid.worker_profile.trades.add(self.electrical)
        self.plumbing.is_active = False
        self.plumbing.save()
        self.assertEqual(self.owner.post(self.accept_url).json()["code"], "worker_not_eligible")

    def test_worker_with_no_active_trade_left_is_unavailable(self):
        self.plumbing.is_active = False
        self.plumbing.save()
        self.assertEqual(self.owner.post(self.accept_url).json()["code"], "worker_unavailable")

    def test_eligible_quote_still_books_and_same_quote_retry_survives_later_changes(self):
        self.assertTrue(self.owner.get(f"{JOBS}{self.job['id']}/quotes/").json()[0]["worker_eligible"])
        first = self.owner.post(self.accept_url)
        self.assertEqual(first.status_code, 201, first.content)
        self.sajid.worker_profile.trades.set([self.electrical])  # changes after booking
        retry = self.owner.post(self.accept_url)
        self.assertEqual((retry.status_code, retry.json()["id"]), (200, first.json()["id"]))
        self.assertEqual(Booking.objects.count(), 1)


class SelfRegisteredWorkerTests(MarketplaceTestCase):
    def test_signup_scan_profile_then_bookable(self):
        worker = Session()
        worker.refresh_csrf()
        signup = worker.post("/api/v1/auth/register/worker/", {"username": "self_made", "password": PASSWORD})
        self.assertEqual(signup.json()["role"], "worker")
        worker.refresh_csrf()
        # Not discoverable before onboarding.
        found = self.session(self.ayesha).get(DISCOVER, trade=self.carpentry.id, service_area=self.g13.id).json()
        self.assertEqual(found["count"], 0)
        scan = worker.post("/api/v1/workers/me/scan/", {"image": upload("photo.png", PNG, "image/png")},
                           multipart=True).json()
        self.assertEqual((scan["registry"], scan["simulated"]), ("fictional", True))
        profile = worker.put("/api/v1/workers/me/", {
            "display_name": "Self Made", "experience_years": 4, "trades": [self.carpentry.id],
            "service_areas": [self.g13.id], "scan_proof": scan["scan_proof"]})
        self.assertEqual(profile.status_code, 201, profile.content)
        self.assertEqual(profile.json()["verification"]["registry"], "fictional")

        customer = self.session(self.ayesha)
        cards = customer.get(DISCOVER, trade=self.carpentry.id, service_area=self.g13.id).json()["results"]
        self.assertEqual([c["display_name"] for c in cards], ["Self Made"])
        self.assertEqual(cards[0]["verification_registry"], "fictional")
        job = self.post_job(customer, trade=self.carpentry.id, service_area=self.g13.id,
                            description="Door hinge").json()
        quote = worker.post(f"{JOBS}{job['id']}/quotes/", {"amount": "900"}).json()
        booking = customer.post(f"/api/v1/quotes/{quote['id']}/accept/")
        self.assertEqual((booking.status_code, booking.json()["status"]), (201, "BOOKED"))
