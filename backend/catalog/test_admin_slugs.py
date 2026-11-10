"""Admin slug normalization: case variants are form errors, never HTTP 500."""

from django.test import Client, TestCase

from accounts.models import User
from config.testing import PASSWORD

from .models import Specialty, Trade

INLINE = {
    "specialties-INITIAL_FORMS": "0", "specialties-MIN_NUM_FORMS": "0", "specialties-MAX_NUM_FORMS": "1000",
}


def specialty_rows(*slugs):
    data = {"specialties-TOTAL_FORMS": str(len(slugs)), **INLINE}
    for i, slug in enumerate(slugs):
        data.update({
            f"specialties-{i}-slug": slug, f"specialties-{i}-name_en": f"Name {i}",
            f"specialties-{i}-name_ur": "نام", f"specialties-{i}-sort_order": "10",
            f"specialties-{i}-is_active": "on",
        })
    return data


class SpecialtySlugAdminTests(TestCase):
    def setUp(self):
        self.admin = Client()
        self.admin.force_login(User.objects.create_superuser("staff", password=PASSWORD))

    def add_trade(self, *slugs, trade_slug="painting"):
        return self.admin.post("/admin/catalog/trade/add/", {
            "slug": trade_slug, "name_en": "Painting", "name_ur": "رنگ", "icon_key": "", "sort_order": "50",
            "is_active": "on", **specialty_rows(*slugs),
        })

    def test_case_variants_in_one_inline_are_a_form_error(self):
        response = self.add_trade("Wall-Paint", "wall-paint")
        self.assertEqual(response.status_code, 200)  # form re-rendered, not a 500
        self.assertContains(response, "Please correct the duplicate data")
        self.assertFalse(Trade.objects.filter(slug="painting").exists())
        self.assertFalse(Specialty.objects.exists())

    def test_slug_is_stored_lowercase(self):
        response = self.add_trade("Wall-Paint", trade_slug="Painting")
        self.assertEqual(response.status_code, 302)
        trade = Trade.objects.get()
        self.assertEqual((trade.slug, list(trade.specialties.values_list("slug", flat=True))),
                         ("painting", ["wall-paint"]))

    def test_case_variant_of_existing_specialty_is_a_form_error(self):
        trade = Trade.objects.create(slug="painting", name_en="Painting", name_ur="رنگ")
        Specialty.objects.create(trade=trade, slug="wall-paint", name_en="Wall", name_ur="دیوار")
        response = self.admin.post("/admin/catalog/specialty/add/", {
            "trade": trade.id, "slug": "WALL-PAINT", "name_en": "Wall 2", "name_ur": "دیوار", "sort_order": "1",
            "is_active": "on"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This trade already has a specialty with this slug.")
        self.assertEqual(Specialty.objects.count(), 1)

    def test_case_variant_trade_slug_is_a_form_error(self):
        Trade.objects.create(slug="painting", name_en="Painting", name_ur="رنگ")
        response = self.add_trade(trade_slug="PAINTING")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Trade with this Slug already exists.")
        self.assertEqual(Trade.objects.count(), 1)
