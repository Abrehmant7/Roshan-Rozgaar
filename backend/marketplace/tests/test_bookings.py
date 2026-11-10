import threading
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from catalog.models import ServiceArea, Trade
from config.api import ApiError
from config.testing import make_user, make_worker

from .. import services
from ..models import ArrivalPin, Booking, JobRequest, Quote
from .base import BOARD, DISCOVER, JOBS, MarketplaceTestCase


class BookingFlowBase(MarketplaceTestCase):
    def setUp(self):
        self.owner = self.session(self.ayesha)
        self.akram_api = self.session(self.akram)
        self.naveed_api = self.session(self.naveed)
        self.job = self.post_job(self.owner, voice=self.WEBM).json()
        self.job_url = f"{JOBS}{self.job['id']}/"

    def quote(self, api, job_id=None, amount="1500.00", message="Can come in 1 hour"):
        return api.post(f"{JOBS}{job_id or self.job['id']}/quotes/", {"amount": amount, "message": message})

    def accept(self, api, quote_id):
        return api.post(f"/api/v1/quotes/{quote_id}/accept/")

    def book_akram(self):
        quote = self.quote(self.akram_api).json()
        booking = self.accept(self.owner, quote["id"]).json()
        return booking, f"/api/v1/bookings/{booking['id']}/"


class QuoteTests(BookingFlowBase):
    def test_submit_and_idempotent_retry(self):
        first = self.quote(self.akram_api)
        self.assertEqual(first.status_code, 201, first.content)
        body = first.json()
        self.assertEqual((body["amount"], body["currency"], body["status"]), ("1500.00", "PKR", "PENDING"))
        retry = self.quote(self.akram_api, amount="1500")
        self.assertEqual(retry.status_code, 200)
        self.assertEqual(retry.json()["id"], body["id"])
        changed = self.quote(self.akram_api, amount="1800")
        self.assertEqual(changed.status_code, 409)
        self.assertEqual(changed.json()["code"], "quote_exists")
        self.assertEqual(Quote.objects.count(), 1)

    def test_quote_validation_and_eligibility(self):
        for amount in ("0", "-5", "abc", "12.345"):
            with self.subTest(amount=amount):
                self.assertIn("amount", self.quote(self.akram_api, amount=amount).json())
        self.assertEqual(self.quote(self.session(self.sajid)).status_code, 404)  # plumber
        self.assertEqual(self.quote(self.session(self.rashid)).status_code, 404)  # wrong area
        self.assertEqual(self.quote(self.owner).json()["code"], "worker_role_required")
        self.naveed.worker_profile.accepting_jobs = False
        self.naveed.worker_profile.save()
        self.assertEqual(self.quote(self.naveed_api).json()["code"], "worker_unavailable")

    def test_quote_visibility(self):
        akram_q = self.quote(self.akram_api).json()
        self.quote(self.naveed_api, amount="1200").json()
        owner_view = self.owner.get(f"{self.job_url}quotes/").json()
        self.assertEqual([q["amount"] for q in owner_view], ["1200.00", "1500.00"])
        self.assertEqual(owner_view[1]["worker"]["display_name"], "Akram")
        self.assertTrue(owner_view[1]["worker"]["is_available"])
        mine = self.akram_api.get(f"{self.job_url}quotes/").json()
        self.assertEqual([q["id"] for q in mine], [akram_q["id"]])
        detail = self.owner.get(self.job_url).json()
        self.assertEqual(len(detail["quotes"]), 2)
        board = self.akram_api.get(BOARD).json()
        self.assertEqual(board["results"][0]["my_quote"]["id"], akram_q["id"])
        self.assertTrue(board["worker_is_available"])
        self.assertEqual(self.owner.get(JOBS).json()["results"][0]["quote_count"], 2)
        self.assertEqual(self.akram_api.get("/api/v1/quotes/").json()["results"][0]["job_summary"]["status"], "OPEN")


class AcceptTests(BookingFlowBase):
    def test_accept_creates_booking_and_changes_visibility(self):
        akram_q = self.quote(self.akram_api).json()
        naveed_q = self.quote(self.naveed_api, amount="1200").json()
        response = self.accept(self.owner, akram_q["id"])
        self.assertEqual(response.status_code, 201, response.content)
        booking = response.json()
        self.assertEqual((booking["status"], booking["amount"], booking["viewer"]), ("BOOKED", "1500.00", "customer"))
        self.assertEqual(booking["actions"], ["issue_pin", "report"])
        self.assertEqual(booking["worker"]["display_name"], "Akram")
        self.assertFalse(booking["worker"]["is_available"])

        self.assertEqual(self.accept(self.owner, akram_q["id"]).status_code, 200)  # same-quote retry
        competing = self.accept(self.owner, naveed_q["id"])
        self.assertEqual((competing.status_code, competing.json()["code"]), (409, "request_already_booked"))
        self.assertEqual(Booking.objects.count(), 1)

        self.assertEqual(self.owner.get(self.job_url).json()["status"], "BOOKED")
        self.assertEqual(self.naveed_api.get(BOARD).json()["count"], 0)
        self.assertEqual(self.naveed_api.get(self.job_url).status_code, 404)
        self.assertEqual(self.naveed_api.get(f"{self.job_url}voice-note/").status_code, 404)
        assigned = self.akram_api.get(self.job_url).json()
        self.assertEqual(assigned["viewer"], "assigned_worker")
        self.assertEqual(assigned["address_details"], "House 12, Street 4")
        self.assertEqual(self.akram_api.get(f"{self.job_url}voice-note/").status_code, 200)
        statuses = {q["id"]: q["status"] for q in self.owner.get(f"{self.job_url}quotes/").json()}
        self.assertEqual(statuses, {akram_q["id"]: "ACCEPTED", naveed_q["id"]: "NOT_SELECTED"})
        late = self.quote(self.naveed_api, amount="1200")
        self.assertEqual(late.json()["code"], "request_not_open")

        found = self.owner.get(DISCOVER, trade=self.electrical.id, service_area=self.g11.id).json()
        self.assertEqual([w["display_name"] for w in found["results"]], ["Naveed"])  # Akram is busy

    def test_worker_cannot_be_booked_on_two_requests(self):
        bilal = self.session(self.bilal)
        other_job = self.post_job(bilal).json()
        q1 = self.quote(self.akram_api).json()
        q2 = self.quote(self.akram_api, job_id=other_job["id"]).json()
        self.assertEqual(self.accept(self.owner, q1["id"]).status_code, 201)
        second = self.accept(bilal, q2["id"])
        self.assertEqual((second.status_code, second.json()["code"]), (409, "worker_unavailable"))
        busy = self.quote(self.akram_api, job_id=self.post_job(bilal).json()["id"])
        self.assertEqual(busy.json()["code"], "worker_unavailable")
        self.assertFalse(self.akram_api.get(BOARD).json()["worker_is_available"])

    def test_accept_permissions(self):
        quote = self.quote(self.akram_api).json()
        self.assertEqual(self.accept(self.session(self.bilal), quote["id"]).status_code, 404)
        self.assertEqual(self.accept(self.akram_api, quote["id"]).json()["code"], "customer_role_required")
        self.assertEqual(self.accept(self.owner, 999999).status_code, 404)
        self.assertEqual(self.owner.post(f"/api/v1/quotes/{quote['id']}/accept/", csrf=False).status_code, 403)

    def test_booking_privacy(self):
        _, url = self.book_akram()
        for user in (self.bilal, self.naveed, self.sajid):
            with self.subTest(user=user.username):
                self.assertEqual(self.session(user).get(url).status_code, 404)
        self.assertEqual(self.owner.get("/api/v1/bookings/").json()["count"], 1)
        self.assertEqual(self.akram_api.get("/api/v1/bookings/?status=BOOKED").json()["count"], 1)
        self.assertEqual(self.session(self.bilal).get("/api/v1/bookings/").json()["count"], 0)


class PinAndCompletionTests(BookingFlowBase):
    def setUp(self):
        super().setUp()
        self.booking, self.url = self.book_akram()

    def issue(self):
        return self.owner.post(f"{self.url}pin/")

    def check_in(self, pin, api=None):
        return (api or self.akram_api).post(f"{self.url}check-in/", {"pin": pin})

    def test_happy_path_to_completion_releases_availability(self):
        self.assertEqual(self.check_in("123456").json()["code"], "no_active_pin")
        issued = self.issue()
        self.assertEqual(issued.status_code, 201)
        pin = issued.json()["pin"]
        self.assertRegex(pin, r"^\d{6}$")
        record = ArrivalPin.objects.get()
        self.assertNotIn(pin, record.digest)

        worker_view = self.akram_api.get(self.url).json()
        self.assertEqual(worker_view["actions"], ["check_in", "report"])
        self.assertIsNotNone(worker_view["active_pin"])
        self.assertNotIn(pin, str(worker_view))
        self.assertNotIn(pin, str(self.owner.get(self.url).json()))

        self.assertEqual(self.akram_api.post(f"{self.url}complete/").json()["code"], "check_in_required")
        done = self.check_in(pin)
        self.assertEqual(done.status_code, 200, done.content)
        self.assertEqual((done.json()["status"], done.json()["actions"]), ("IN_PROGRESS", ["complete", "report"]))
        replay = self.check_in(pin)
        self.assertEqual((replay.status_code, replay.json()["code"]), (409, "invalid_booking_status"))
        self.assertEqual(self.issue().json()["code"], "invalid_booking_status")

        completed = self.akram_api.post(f"{self.url}complete/")
        self.assertEqual(completed.json()["status"], "COMPLETED")
        self.assertIsNotNone(completed.json()["completed_at"])
        self.assertEqual(self.akram_api.post(f"{self.url}complete/").status_code, 200)  # retry-safe
        self.assertEqual(self.owner.get(self.job_url).json()["status"], "COMPLETED")
        found = self.owner.get(DISCOVER, trade=self.electrical.id, service_area=self.g11.id).json()
        self.assertIn("Akram", [w["display_name"] for w in found["results"]])

    def test_wrong_pin_attempts_persist_and_lock(self):
        pin = self.issue().json()["pin"]
        wrong = "000000" if pin != "000000" else "111111"
        first = self.check_in(wrong)
        self.assertEqual((first.status_code, first.json()["code"], first.json()["attempts_remaining"]),
                         (400, "pin_incorrect", 4))
        self.assertEqual(ArrivalPin.objects.get().failed_attempts, 1)
        for _ in range(3):
            self.check_in(wrong)
        locked = self.check_in(wrong)
        self.assertEqual(locked.json()["code"], "pin_locked")
        self.assertEqual(self.check_in(pin).json()["code"], "no_active_pin")
        self.assertIn("pin", self.check_in("12ab").json())

    def test_expired_and_replaced_pins(self):
        old = self.issue().json()["pin"]
        new = self.issue().json()["pin"]
        if old != new:
            self.assertEqual(self.check_in(old).json()["code"], "pin_incorrect")
        self.assertEqual(ArrivalPin.objects.filter(revoked_at__isnull=False).count(), 1)
        ArrivalPin.objects.filter(revoked_at__isnull=True).update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.check_in(new).json()["code"], "pin_expired")
        self.assertEqual(self.check_in(new).json()["code"], "no_active_pin")

    @override_settings(PIN_ISSUE_LIMIT=3)
    def test_issue_throttle_and_roles(self):
        for _ in range(3):
            self.assertEqual(self.issue().status_code, 201)
        throttled = self.issue()
        self.assertEqual((throttled.status_code, throttled.json()["code"]), (429, "pin_issue_throttled"))
        self.assertEqual(self.akram_api.post(f"{self.url}pin/").json()["code"], "customer_role_required")
        self.assertEqual(self.session(self.bilal).post(f"{self.url}pin/").status_code, 404)
        self.assertEqual(self.check_in("123456", api=self.naveed_api).status_code, 404)
        self.assertEqual(self.owner.post(f"{self.url}complete/").json()["code"], "worker_role_required")


class ConcurrencyTests(TransactionTestCase):
    """Real PostgreSQL row locks with parallel connections."""

    def setUp(self):
        call_command("seed_catalog", stdout=StringIO())
        electrical, g11 = Trade.objects.get(slug="electrical"), ServiceArea.objects.get(sector_code="G-11")
        self.customer_a, self.customer_b = make_user("cust_a"), make_user("cust_b")
        self.w1 = make_worker("w_one", [electrical], [g11])
        self.w2 = make_worker("w_two", [electrical], [g11])
        self.job_a = JobRequest.objects.create(customer=self.customer_a, trade=electrical, service_area=g11,
                                               description="A")
        self.job_b = JobRequest.objects.create(customer=self.customer_b, trade=electrical, service_area=g11,
                                               description="B")

    def race(self, calls):
        barrier = threading.Barrier(len(calls))
        results = [None] * len(calls)

        def run(i, fn):
            try:
                barrier.wait()
                results[i] = ("ok", fn())
            except ApiError as exc:
                results[i] = ("error", exc.detail.code)
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(calls)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        return results

    def test_competing_acceptances_on_one_request(self):
        q1 = Quote.objects.create(job=self.job_a, worker=self.w1, amount=1000)
        q2 = Quote.objects.create(job=self.job_a, worker=self.w2, amount=900)
        results = self.race([lambda: services.accept_quote(self.customer_a, q1.pk),
                             lambda: services.accept_quote(self.customer_a, q2.pk)])
        outcomes = sorted(r[0] for r in results)
        self.assertEqual(outcomes, ["error", "ok"], results)
        self.assertIn(("error", "request_already_booked"), results)
        self.assertEqual(Booking.objects.filter(job=self.job_a).count(), 1)

    def test_one_worker_accepted_on_two_requests_at_once(self):
        qa = Quote.objects.create(job=self.job_a, worker=self.w1, amount=1000)
        qb = Quote.objects.create(job=self.job_b, worker=self.w1, amount=1100)
        results = self.race([lambda: services.accept_quote(self.customer_a, qa.pk),
                             lambda: services.accept_quote(self.customer_b, qb.pk)])
        self.assertEqual(sorted(r[0] for r in results), ["error", "ok"], results)
        self.assertIn(("error", "worker_unavailable"), results)
        self.assertEqual(Booking.objects.filter(worker=self.w1).count(), 1)

    def test_parallel_identical_accepts_return_one_booking(self):
        q1 = Quote.objects.create(job=self.job_a, worker=self.w1, amount=1000)
        results = self.race([lambda: services.accept_quote(self.customer_a, q1.pk) for _ in range(3)])
        self.assertTrue(all(r[0] == "ok" for r in results), results)
        self.assertEqual(sorted(r[1][1] for r in results), [False, False, True])
        self.assertEqual(Booking.objects.count(), 1)
