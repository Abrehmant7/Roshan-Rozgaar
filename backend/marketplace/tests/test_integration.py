"""Phase 7: the whole product through the HTTP API with two independent sessions."""

from io import StringIO

from django.core.management import call_command
from django.test import Client, override_settings

from accounts.models import User
from catalog.models import ServiceArea, Specialty, Trade
from config.testing import PASSWORD, PNG, Session, make_user, upload
from workers.models import WorkerProfile

from ..models import Booking, JobRequest, Report, Review
from .base import BOARD, DISCOVER, JOBS, MarketplaceTestCase


class TwoRoleWalkthrough(MarketplaceTestCase):
    def test_full_flow_in_carpentry(self):
        carpentry = self.carpentry
        doors = Specialty.objects.get(trade=carpentry, slug="door-window")
        g13 = self.g13

        # Worker: sign in (staff-provisioned account) and onboard through the mock ID scan.
        worker_user = make_user("ustad_tariq", role="worker")
        worker = Session(worker_user)
        scan = worker.post("/api/v1/workers/me/scan/", {"image": upload("card-6.jpg", PNG, "image/png")},
                           multipart=True).json()
        self.assertEqual((scan["mode"], scan["identity"]["name_en"]), ("mock", "Tariq Javed"))
        profile = worker.put("/api/v1/workers/me/", {
            "display_name": "Tariq Carpenter", "experience_years": 20, "trades": [carpentry.id],
            "specialties": [doors.id], "service_areas": [g13.id], "scan_proof": scan["scan_proof"],
        })
        self.assertEqual(profile.status_code, 201, profile.content)
        self.assertTrue(profile.json()["is_available"])

        # Customer: register, discover, post a typed + voice request.
        customer = Session()
        customer.refresh_csrf()
        reg = customer.post("/api/v1/auth/register/", {"username": "new_customer", "password": PASSWORD})
        self.assertEqual(reg.json()["role"], "customer")
        customer.refresh_csrf()
        found = customer.get(DISCOVER, trade=carpentry.id, service_area=g13.id, specialty=doors.id).json()
        self.assertEqual([w["display_name"] for w in found["results"]], ["Tariq Carpenter"])
        self.assertEqual(found["results"][0]["rating"], {"average": None, "count": 0})
        job = customer.post(JOBS, {"trade": carpentry.id, "service_area": g13.id, "specialty": doors.id,
                                   "description": "Cupboard door off its hinge", "address_details": "Flat 3",
                                   "voice_note": upload("note.webm", self.WEBM, "audio/webm")},
                            multipart=True).json()
        self.assertEqual(job["status"], "OPEN")

        # Worker: board shows it, plays the note, quotes.
        board = worker.get(BOARD).json()
        self.assertEqual([j["id"] for j in board["results"]], [job["id"]])
        self.assertEqual(worker.get(job["voice_note_url"]).status_code, 200)
        quote = worker.post(f"{JOBS}{job['id']}/quotes/", {"amount": "2200", "message": "Today 5pm"}).json()

        # Customer: sees the quote, accepts.
        quotes = customer.get(f"{JOBS}{job['id']}/quotes/").json()
        self.assertEqual([(q["amount"], q["worker"]["display_name"]) for q in quotes], [("2200.00", "Tariq Carpenter")])
        booking = customer.post(f"/api/v1/quotes/{quote['id']}/accept/").json()
        self.assertEqual(booking["status"], "BOOKED")
        url = f"/api/v1/bookings/{booking['id']}/"

        # Search and board change at acceptance.
        self.assertEqual(customer.get(DISCOVER, trade=carpentry.id, service_area=g13.id).json()["count"], 0)
        self.assertEqual(worker.get(BOARD).json()["count"], 0)
        self.assertFalse(worker.get("/api/v1/workers/me/dashboard/").json()["is_available"])

        # Arrival PIN, check-in, completion.
        pin = customer.post(f"{url}pin/").json()["pin"]
        self.assertEqual(worker.post(f"{url}check-in/", {"pin": pin}).json()["status"], "IN_PROGRESS")
        self.assertEqual(worker.post(f"{url}complete/").json()["status"], "COMPLETED")

        # Review and two-way reports; staff sees the reports.
        self.assertEqual(customer.post(f"{url}review/", {"rating": 5, "tags": ["on_time"]}).status_code, 201)
        self.assertEqual(customer.post(f"{url}reports/", {"reason": "other", "details": "Test"}).status_code, 201)
        self.assertEqual(worker.post(f"{url}reports/", {"reason": "payment_dispute"}).status_code, 201)
        staff = Client()
        staff.force_login(User.objects.create_superuser("staff", password=PASSWORD))
        self.assertContains(staff.get("/admin/marketplace/report/?status__exact=OPEN"), "Payment dispute")
        self.assertEqual(Report.objects.count(), 2)

        # Availability returns, with the new rating.
        again = customer.get(DISCOVER, trade=carpentry.id, service_area=g13.id).json()["results"]
        self.assertEqual(again[0]["rating"], {"average": 5.0, "count": 1})
        self.assertEqual(again[0]["completed_jobs"], 1)
        self.assertTrue(worker.get("/api/v1/workers/me/").json()["is_available"])

    def test_trade_added_in_admin_works_through_same_api(self):
        staff = Client()
        staff.force_login(User.objects.create_superuser("staff", password=PASSWORD))
        staff.post("/admin/catalog/trade/add/", {
            "slug": "painting", "name_en": "Painting", "name_ur": "رنگ و روغن", "sort_order": 50, "is_active": "on",
            "specialties-TOTAL_FORMS": "0", "specialties-INITIAL_FORMS": "0",
            "specialties-MIN_NUM_FORMS": "0", "specialties-MAX_NUM_FORMS": "1000"})
        staff.post("/admin/catalog/servicearea/add/", {
            "city": "Islamabad", "sector_code": "e 11", "name_en": "E-11", "name_ur": "ای-11",
            "sort_order": 90, "is_active": "on"})
        painting = Trade.objects.get(slug="painting")
        e11 = ServiceArea.objects.get(sector_code="E-11")
        painter = make_user("painter", role="worker")
        painter_api = Session(painter)
        proof = painter_api.post("/api/v1/workers/me/scan/", {"image": upload("card-5.png", PNG, "image/png")},
                                 multipart=True).json()["scan_proof"]
        painter_api.put("/api/v1/workers/me/", {"display_name": "Painter", "experience_years": 3,
                                                "trades": [painting.id], "service_areas": [e11.id],
                                                "scan_proof": proof})
        customer = self.session(self.ayesha)
        self.assertEqual(customer.get(DISCOVER, trade=painting.id, service_area=e11.id).json()["count"], 1)
        job = self.post_job(customer, trade=painting.id, service_area=e11.id, description="Paint one room")
        self.assertEqual(job.status_code, 201)
        self.assertEqual(painter_api.get(BOARD).json()["results"][0]["trade"]["name_ur"], "رنگ و روغن")


@override_settings(DEBUG=True)
class SeedDemoTests(MarketplaceTestCase):
    def test_idempotent_and_preserves_edits(self):
        call_command("seed_demo", stdout=StringIO())
        counts = (User.objects.count(), WorkerProfile.objects.count(), JobRequest.objects.count(),
                  Booking.objects.count(), Review.objects.count())
        rashid = WorkerProfile.objects.get(user__username="demo_rashid")
        rashid.display_name = "Edited by team"
        rashid.save()
        call_command("seed_demo", stdout=StringIO())
        self.assertEqual(counts, (User.objects.count(), WorkerProfile.objects.count(), JobRequest.objects.count(),
                                  Booking.objects.count(), Review.objects.count()))
        self.assertEqual(WorkerProfile.objects.get(user__username="demo_rashid").display_name, "Edited by team")
        self.assertFalse(WorkerProfile.objects.filter(user__username__in=["demo_imran", "demo_tariq"]).exists())
        self.assertTrue(User.objects.get(username="demo_akram").check_password("RozgarDemo#2026"))
        ayesha = Session()
        ayesha.login(User.objects.get(username="demo_ayesha"), password="RozgarDemo#2026")
        card = ayesha.get(f"/api/v1/workers/{User.objects.get(username='demo_akram').id}/").json()
        self.assertEqual(card["rating"], {"average": 4.5, "count": 2})

    def test_reset_onboarding_only_touches_fresh_accounts(self):
        call_command("seed_demo", stdout=StringIO())
        imran = User.objects.get(username="demo_imran")
        api = Session()
        api.login(imran, password="RozgarDemo#2026")
        proof = api.post("/api/v1/workers/me/scan/", {"image": upload("card-5.png", PNG, "image/png")},
                         multipart=True).json()["scan_proof"]
        api.put("/api/v1/workers/me/", {"display_name": "Imran", "experience_years": 4,
                                        "trades": [self.electrical.id], "service_areas": [self.g11.id],
                                        "scan_proof": proof})
        ready = WorkerProfile.objects.filter(user__username__startswith="demo_").count()
        call_command("seed_demo", "--reset-onboarding", stdout=StringIO())
        self.assertEqual(WorkerProfile.objects.filter(user__username__startswith="demo_").count(), ready - 1)
        self.assertTrue(WorkerProfile.objects.filter(user__username="demo_akram").exists())

    @override_settings(DEBUG=False)
    def test_refuses_without_debug(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())
