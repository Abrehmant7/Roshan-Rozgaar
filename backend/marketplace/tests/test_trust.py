from django.test import Client

from accounts.models import User
from config.testing import PASSWORD

from ..models import Report, Review
from .base import DISCOVER, MarketplaceTestCase
from .test_bookings import BookingFlowBase


class CompletedBookingBase(BookingFlowBase):
    def complete_booking(self, worker_api=None, owner=None, url=None):
        worker_api, owner, url = worker_api or self.akram_api, owner or self.owner, url or self.url
        pin = owner.post(f"{url}pin/").json()["pin"]
        worker_api.post(f"{url}check-in/", {"pin": pin})
        return worker_api.post(f"{url}complete/").json()

    def setUp(self):
        super().setUp()
        self.booking, self.url = self.book_akram()

    def review(self, api=None, **body):
        body = {"rating": 5, "text": "Fixed it fast", "tags": ["on_time", "fair_price"], **body}
        return (api or self.owner).post(f"{self.url}review/", body)


class ReviewTests(CompletedBookingBase):
    def test_review_rules_and_stats(self):
        early = self.review()
        self.assertEqual((early.status_code, early.json()["code"]), (409, "booking_not_completed"))
        self.complete_booking()
        self.assertEqual(self.owner.get(self.url).json()["actions"], ["review", "report"])

        self.assertEqual(self.review(api=self.akram_api).json()["code"], "customer_role_required")
        self.assertEqual(self.review(api=self.session(self.bilal)).status_code, 404)
        self.assertIn("rating", self.review(rating=6).json())
        self.assertIn("tags", self.review(tags=["made_up"]).json())

        created = self.review()
        self.assertEqual(created.status_code, 201, created.content)
        self.assertEqual(created.json()["tags"], ["on_time", "fair_price"])
        duplicate = self.review(rating=1)
        self.assertEqual((duplicate.status_code, duplicate.json()["code"]), (409, "review_exists"))
        review = Review.objects.get()
        self.assertEqual((review.customer_id, review.worker_id), (self.ayesha.id, self.akram.id))

        view = self.owner.get(self.url).json()
        self.assertEqual(view["review"]["rating"], 5)
        self.assertEqual(view["actions"], ["report"])
        card = self.owner.get(f"/api/v1/workers/{self.akram.id}/").json()
        self.assertEqual(card["rating"], {"average": 5.0, "count": 1})
        self.assertEqual(card["completed_jobs"], 1)
        self.assertEqual(card["recent_reviews"][0]["text"], "Fixed it fast")
        self.assertNotIn("customer", card["recent_reviews"][0])

    def test_new_worker_state_and_rating_ranking(self):
        naveed = self.owner.get(f"/api/v1/workers/{self.naveed.id}/").json()
        self.assertEqual((naveed["rating"], naveed["completed_jobs"]), ({"average": None, "count": 0}, 0))
        self.complete_booking()
        self.review(rating=4)
        found = self.owner.get(DISCOVER, trade=self.electrical.id, service_area=self.g11.id).json()["results"]
        self.assertEqual([w["display_name"] for w in found], ["Akram", "Naveed"])  # rated before unrated
        self.assertEqual(found[0]["rating"]["average"], 4.0)
        # specialty match still outranks rating
        self.naveed.worker_profile.specialties.set([self.fan])
        found = self.owner.get(DISCOVER, trade=self.electrical.id, service_area=self.g11.id,
                               specialty=self.fan.id).json()["results"]
        self.assertEqual([w["display_name"] for w in found], ["Naveed", "Akram"])

    def test_unknown_or_incomplete_worker_profile_is_404(self):
        self.assertEqual(self.owner.get(f"/api/v1/workers/{self.newbie.id}/").status_code, 404)
        self.assertEqual(self.owner.get("/api/v1/workers/999999/").status_code, 404)

    def test_tags_and_reasons_are_public(self):
        tags = Client().get("/api/v1/reviews/tags/").json()
        self.assertIn({"key": "on_time", "name_en": "On time", "name_ur": "وقت پر آئے"}, tags)
        reasons = Client().get("/api/v1/reports/reasons/").json()
        self.assertIn("no_show", [r["key"] for r in reasons])


class ReportTests(CompletedBookingBase):
    def report(self, api, **body):
        return api.post(f"{self.url}reports/", {"reason": "no_show", "details": "Came 2 hours late", **body})

    def test_both_directions_private_and_unique(self):
        by_customer = self.report(self.owner)
        self.assertEqual(by_customer.status_code, 201, by_customer.content)
        self.assertEqual(by_customer.json()["status"], "OPEN")
        by_worker = self.report(self.akram_api, reason="payment_dispute", details="")
        self.assertEqual(by_worker.status_code, 201)
        subjects = dict(Report.objects.values_list("reporter_id", "subject_id"))
        self.assertEqual(subjects, {self.ayesha.id: self.akram.id, self.akram.id: self.ayesha.id})

        again = self.report(self.owner)
        self.assertEqual((again.status_code, again.json()["code"]), (409, "report_exists"))
        self.assertEqual(self.report(self.session(self.bilal)).status_code, 404)
        self.assertEqual(self.report(self.naveed_api).status_code, 404)
        self.assertIn("reason", self.report(self.owner, reason="nope").json())

        mine = self.owner.get("/api/v1/reports/").json()
        self.assertEqual([r["reason"] for r in mine["results"]], ["no_show"])
        self.assertEqual(self.akram_api.get("/api/v1/reports/").json()["results"][0]["reason"], "payment_dispute")
        self.assertEqual(self.session(self.bilal).get("/api/v1/reports/").json()["count"], 0)
        self.assertEqual(self.owner.get(self.url).json()["my_report"]["status"], "OPEN")
        self.assertNotIn("report", self.owner.get(self.url).json()["actions"])
        card = self.owner.get(f"/api/v1/workers/{self.akram.id}/").content.decode()
        self.assertNotIn("Came 2 hours late", card)

    def test_staff_find_and_resolve_in_admin(self):
        report_id = self.report(self.owner).json()["id"]
        staff = User.objects.create_superuser("mod", password=PASSWORD)
        admin = Client()
        admin.force_login(staff)
        queue = admin.get("/admin/marketplace/report/?status__exact=OPEN")
        self.assertContains(queue, f"/admin/marketplace/report/{report_id}/change/")
        response = admin.post("/admin/marketplace/report/", {
            "action": "mark_resolved", "_selected_action": [report_id]})
        self.assertEqual(response.status_code, 302)
        report = Report.objects.get(pk=report_id)
        self.assertEqual((report.status, report.resolved_by_id), ("RESOLVED", staff.id))
        self.assertIsNotNone(report.resolved_at)
        self.assertEqual(self.owner.get("/api/v1/reports/").json()["results"][0]["status"], "RESOLVED")


class DashboardTests(CompletedBookingBase):
    def test_dashboard_tracks_booking_lifecycle(self):
        dash = self.akram_api.get("/api/v1/workers/me/dashboard/").json()
        self.assertEqual(dash["profile_status"], "complete")
        self.assertFalse(dash["is_available"])
        self.assertEqual(dash["active_booking"]["id"], self.booking["id"])
        self.assertEqual(dash["active_booking"]["actions"], ["check_in", "report"])
        self.complete_booking()
        self.review(rating=4)
        dash = self.akram_api.get("/api/v1/workers/me/dashboard/").json()
        self.assertTrue(dash["is_available"])
        self.assertIsNone(dash["active_booking"])
        self.assertEqual((dash["completed_jobs"], dash["rating"]), (1, {"average": 4.0, "count": 1}))
        self.assertEqual(dash["recent_jobs"][0]["rating"], 4)
        self.assertEqual(dash["recent_jobs"][0]["status"], "COMPLETED")

    def test_dashboard_scoping(self):
        self.assertEqual(self.session(self.newbie).get("/api/v1/workers/me/dashboard/").json()["profile_status"],
                         "missing")
        self.assertEqual(self.owner.get("/api/v1/workers/me/dashboard/").json()["code"], "worker_role_required")
        naveed = self.naveed_api.get("/api/v1/workers/me/dashboard/").json()
        self.assertIsNone(naveed["active_booking"])
        self.assertEqual(naveed["recent_jobs"], [])
