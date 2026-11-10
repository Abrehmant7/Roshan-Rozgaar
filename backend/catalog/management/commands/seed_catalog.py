"""Seed starter catalog data.

Idempotent and non-destructive: records are matched on their natural key
(trade slug; trade + specialty slug; city + sector code) and only created when
missing. Existing records are never updated, so names, sort orders and
retirements (is_active=False) made in Admin survive re-runs.
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import ServiceArea, Specialty, Trade, normalize_sector_code

# (slug, name_en, name_ur, icon_key, [(slug, name_en, name_ur), ...])
TRADES = [
    ("plumbing", "Plumbing", "پلمبنگ", "droplet", [
        ("leak-repair", "Leak repair", "لیکیج کی مرمت"),
        ("tap-fitting", "Tap & fitting installation", "نل اور فٹنگ لگانا"),
        ("drain-blockage", "Drain blockage", "نالی کی بندش کھولنا"),
        ("water-tank-motor", "Water tank & motor", "پانی کی ٹینکی اور موٹر"),
    ]),
    ("electrical", "Electrical", "بجلی کا کام", "zap", [
        ("wiring", "Wiring", "وائرنگ"),
        ("fan-installation", "Fan installation", "پنکھا لگانا"),
        ("switchboard-repair", "Switchboard repair", "سوئچ بورڈ کی مرمت"),
        ("ups-inverter", "UPS & inverter", "یو پی ایس اور انورٹر"),
    ]),
    ("ac-repair", "AC Repair", "اے سی مرمت", "snowflake", [
        ("ac-service", "AC service", "اے سی سروس"),
        ("gas-refill", "Gas refill", "گیس بھروانا"),
        ("ac-installation", "AC installation", "اے سی لگانا"),
    ]),
    ("carpentry", "Carpentry", "بڑھئی کا کام", "hammer", [
        ("furniture-repair", "Furniture repair", "فرنیچر کی مرمت"),
        ("door-window", "Door & window fitting", "دروازے اور کھڑکی کی فٹنگ"),
        ("kitchen-cabinets", "Kitchen cabinets", "کچن کیبنٹ"),
    ]),
]

# (city, sector_code, name_en, name_ur)
SERVICE_AREAS = [
    ("Islamabad", "G-11", "G-11", "جی-11"),
    ("Islamabad", "G-13", "G-13", "جی-13"),
    ("Islamabad", "I-10", "I-10", "آئی-10"),
    ("Islamabad", "F-10", "F-10", "ایف-10"),
    ("Islamabad", "G-9", "G-9", "جی-9"),
    ("Islamabad", "I-8", "I-8", "آئی-8"),
]


class Command(BaseCommand):
    help = "Create starter trades, specialties and Islamabad service areas if missing."

    @transaction.atomic
    def handle(self, *args, **options):
        created = {"trades": 0, "specialties": 0, "service areas": 0}
        existing = dict.fromkeys(created, 0)

        for t_order, (slug, name_en, name_ur, icon, specialties) in enumerate(TRADES, start=1):
            trade, was_created = Trade.objects.get_or_create(
                slug=slug,
                defaults={"name_en": name_en, "name_ur": name_ur, "icon_key": icon,
                          "sort_order": t_order * 10},
            )
            (created if was_created else existing)["trades"] += 1

            for s_order, (s_slug, s_en, s_ur) in enumerate(specialties, start=1):
                _, was_created = Specialty.objects.get_or_create(
                    trade=trade,
                    slug=s_slug,
                    defaults={"name_en": s_en, "name_ur": s_ur, "sort_order": s_order * 10},
                )
                (created if was_created else existing)["specialties"] += 1

        for a_order, (city, code, name_en, name_ur) in enumerate(SERVICE_AREAS, start=1):
            code = normalize_sector_code(code)
            if ServiceArea.objects.filter(city__iexact=city, sector_code=code).exists():
                existing["service areas"] += 1
                continue
            ServiceArea.objects.create(city=city, sector_code=code, name_en=name_en,
                                       name_ur=name_ur, sort_order=a_order * 10)
            created["service areas"] += 1

        for key in created:
            self.stdout.write(f"{key}: {created[key]} created, {existing[key]} already present")
        self.stdout.write(self.style.SUCCESS("Catalog seed complete."))
