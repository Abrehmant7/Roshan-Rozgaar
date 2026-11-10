"""Reference data managed by staff in Django Admin.

Entries are retired with `is_active=False` rather than deleted, so later
records (worker profiles, jobs) can keep pointing at them.
"""

import re

from django.db import models
from django.db.models.functions import Lower


class CatalogEntry(models.Model):
    name_en = models.CharField("English name", max_length=100)
    name_ur = models.CharField("Urdu name", max_length=100)
    sort_order = models.PositiveIntegerField(default=0, help_text="Lower numbers are listed first.")
    is_active = models.BooleanField(default=True, help_text="Untick to retire this entry.")

    class Meta:
        abstract = True

    def __str__(self):
        return self.name_en


class Trade(CatalogEntry):
    slug = models.SlugField(max_length=50, unique=True)
    icon_key = models.CharField(
        max_length=50, blank=True, help_text="Optional icon name the frontend maps to an icon."
    )

    class Meta:
        ordering = ["sort_order", "name_en", "id"]

    def clean(self):
        self.slug = self.slug.lower()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class Specialty(CatalogEntry):
    # PROTECT: a trade cannot be deleted while it still has specialties.
    trade = models.ForeignKey(Trade, on_delete=models.PROTECT, related_name="specialties")
    slug = models.SlugField(max_length=50, help_text="Unique within its trade.")

    class Meta:
        verbose_name_plural = "specialties"
        ordering = ["trade__sort_order", "trade__name_en", "sort_order", "name_en", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["trade", "slug"],
                name="catalog_specialty_unique_slug_per_trade",
                violation_error_message="This trade already has a specialty with this slug.",
            )
        ]

    def clean(self):
        self.slug = self.slug.lower()

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


def normalize_city(value: str) -> str:
    return " ".join(value.split())


def normalize_sector_code(value: str) -> str:
    """'g 11', 'g_11', 'G11', ' G-11 ' -> 'G-11'; 'g-11/1' -> 'G-11/1'."""
    code = re.sub(r"[\s_\-]+", "-", value.strip()).upper()
    return re.sub(r"^([A-Z]+)-?(\d)", r"\1-\2", code)


class ServiceArea(CatalogEntry):
    city = models.CharField(max_length=100)
    sector_code = models.CharField(
        max_length=20, help_text="Stored normalized, e.g. 'g 11' is saved as 'G-11'."
    )

    class Meta:
        ordering = ["city", "sort_order", "sector_code", "id"]
        constraints = [
            # Codes are normalized on clean/save; city is compared case-insensitively.
            models.UniqueConstraint(
                Lower("city"),
                "sector_code",
                name="catalog_servicearea_unique_sector_per_city",
                violation_error_message="This city already has a service area with this sector code.",
            )
        ]

    def __str__(self):
        return f"{self.sector_code}, {self.city}"

    def clean(self):
        # Runs before validate_constraints() in full_clean(), so Admin reports
        # duplicates as form errors instead of hitting the database constraint.
        self.city = normalize_city(self.city)
        self.sector_code = normalize_sector_code(self.sector_code)

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
