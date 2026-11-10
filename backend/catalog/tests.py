from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import Client, TestCase

from accounts.models import User

from .models import ServiceArea, Specialty, Trade, normalize_sector_code


def seed():
    call_command("seed_catalog", stdout=StringIO())


def counts():
    return (Trade.objects.count(), Specialty.objects.count(), ServiceArea.objects.count())


class SeedCommandTests(TestCase):
    def test_seed_is_idempotent(self):
        seed()
        first = counts()
        self.assertEqual(first, (4, 14, 6))
        seed()
        self.assertEqual(counts(), first)
        self.assertEqual(
            set(Trade.objects.values_list("slug", flat=True)),
            {"plumbing", "electrical", "ac-repair", "carpentry"},
        )
        self.assertEqual(
            set(ServiceArea.objects.values_list("city", "sector_code")),
            {("Islamabad", c) for c in ("G-11", "G-13", "I-10", "F-10", "G-9", "I-8")},
        )

    def test_seed_preserves_admin_edits(self):
        seed()
        Trade.objects.filter(slug="plumbing").update(name_en="Plumber", sort_order=99)
        Specialty.objects.filter(slug="gas-refill").update(is_active=False)
        ServiceArea.objects.filter(sector_code="G-13").update(name_ur="جی تیرہ")
        seed()
        self.assertEqual(Trade.objects.get(slug="plumbing").name_en, "Plumber")
        self.assertEqual(Trade.objects.get(slug="plumbing").sort_order, 99)
        self.assertFalse(Specialty.objects.get(slug="gas-refill").is_active)
        self.assertEqual(ServiceArea.objects.get(sector_code="G-13").name_ur, "جی تیرہ")
        self.assertEqual(counts(), (4, 14, 6))


class ModelRuleTests(TestCase):
    def test_trade_with_specialties_cannot_be_deleted(self):
        trade = Trade.objects.create(slug="masonry", name_en="Masonry", name_ur="مستری")
        Specialty.objects.create(trade=trade, slug="tiling", name_en="Tiling", name_ur="ٹائلیں")
        with self.assertRaises(ProtectedError):
            trade.delete()

    def test_specialty_slug_unique_within_trade_only(self):
        a = Trade.objects.create(slug="a", name_en="A", name_ur="ا")
        b = Trade.objects.create(slug="b", name_en="B", name_ur="ب")
        Specialty.objects.create(trade=a, slug="repair", name_en="Repair", name_ur="مرمت")
        Specialty.objects.create(trade=b, slug="repair", name_en="Repair", name_ur="مرمت")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Specialty.objects.create(trade=a, slug="repair", name_en="Again", name_ur="دوبارہ")

    def test_sector_code_normalization(self):
        for raw in ("G-11", "g-11", " g 11 ", "G11", "g_11"):
            self.assertEqual(normalize_sector_code(raw), "G-11")
        self.assertEqual(normalize_sector_code("g-11/1"), "G-11/1")

    def test_normalized_sector_code_unique_per_city(self):
        ServiceArea.objects.create(city="Islamabad", sector_code="G-11", name_en="G-11", name_ur="جی-11")
        duplicate = ServiceArea(city=" islamabad ", sector_code="g 11", name_en="x", name_ur="x")
        with self.assertRaises(ValidationError):
            duplicate.full_clean()  # what Admin runs: reported as a form error
        with self.assertRaises(IntegrityError), transaction.atomic():
            duplicate.save()  # and the database enforces it too
        ServiceArea.objects.create(city="Rawalpindi", sector_code="G-11", name_en="x", name_ur="x")


class CatalogApiTests(TestCase):
    def setUp(self):
        seed()
        self.client = Client(enforce_csrf_checks=True)

    def get(self, path):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200, path)
        return response.json()

    def test_endpoints_are_public_and_include_both_names(self):
        trades = self.get("/api/v1/catalog/trades/")
        self.assertEqual([t["slug"] for t in trades], ["plumbing", "electrical", "ac-repair", "carpentry"])
        self.assertEqual(set(trades[0]), {"id", "slug", "name_en", "name_ur", "icon_key"})
        areas = self.get("/api/v1/catalog/service-areas/")
        self.assertEqual([a["sector_code"] for a in areas], ["G-11", "G-13", "I-10", "F-10", "G-9", "I-8"])
        self.assertEqual(set(areas[0]), {"id", "city", "sector_code", "name_en", "name_ur"})

    def test_specialties_are_filtered_by_trade(self):
        plumbing = Trade.objects.get(slug="plumbing")
        electrical = Trade.objects.get(slug="electrical")
        rows = self.get(f"/api/v1/catalog/trades/{plumbing.id}/specialties/")
        self.assertEqual(
            [r["slug"] for r in rows],
            ["leak-repair", "tap-fitting", "drain-blockage", "water-tank-motor"],
        )
        self.assertTrue(all(r["trade"] == plumbing.id for r in rows))
        rows = self.get(f"/api/v1/catalog/trades/{electrical.id}/specialties/")
        self.assertTrue(all(r["trade"] == electrical.id for r in rows))
        self.assertNotIn("leak-repair", [r["slug"] for r in rows])

    def test_inactive_entries_are_hidden(self):
        ac = Trade.objects.get(slug="ac-repair")
        Specialty.objects.filter(slug="leak-repair").update(is_active=False)
        ServiceArea.objects.filter(sector_code="I-10").update(is_active=False)
        ac.is_active = False
        ac.save()

        self.assertNotIn("ac-repair", [t["slug"] for t in self.get("/api/v1/catalog/trades/")])
        self.assertEqual(self.client.get(f"/api/v1/catalog/trades/{ac.id}/specialties/").status_code, 404)
        plumbing = Trade.objects.get(slug="plumbing")
        slugs = [r["slug"] for r in self.get(f"/api/v1/catalog/trades/{plumbing.id}/specialties/")]
        self.assertNotIn("leak-repair", slugs)
        self.assertNotIn("I-10", [a["sector_code"] for a in self.get("/api/v1/catalog/service-areas/")])
        self.assertEqual(self.client.get("/api/v1/catalog/trades/999999/specialties/").status_code, 404)

    def test_trade_added_in_admin_appears_in_api(self):
        staff = User.objects.create_superuser("root", password="Sabz-Chai-4821")
        admin = Client()
        admin.force_login(staff)
        response = admin.post("/admin/catalog/trade/add/", {
            "slug": "painting", "name_en": "Painting", "name_ur": "رنگ و روغن", "icon_key": "paintbrush",
            "sort_order": 50, "is_active": "on",
            "specialties-TOTAL_FORMS": "1", "specialties-INITIAL_FORMS": "0",
            "specialties-MIN_NUM_FORMS": "0", "specialties-MAX_NUM_FORMS": "1000",
            "specialties-0-slug": "wall-paint", "specialties-0-name_en": "Wall painting",
            "specialties-0-name_ur": "دیوار پر رنگ", "specialties-0-sort_order": "10",
            "specialties-0-is_active": "on",
        })
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))

        trades = self.get("/api/v1/catalog/trades/")
        painting = next(t for t in trades if t["slug"] == "painting")
        self.assertEqual(painting["name_ur"], "رنگ و روغن")
        self.assertEqual(trades[-1]["slug"], "painting")  # sort_order 50 > seeded 10..40
        rows = self.get(f"/api/v1/catalog/trades/{painting['id']}/specialties/")
        self.assertEqual([r["slug"] for r in rows], ["wall-paint"])

    def test_catalog_is_read_only(self):
        self.assertEqual(self.client.post("/api/v1/catalog/trades/", {}).status_code, 405)
