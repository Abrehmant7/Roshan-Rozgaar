"""Seed a complete, FICTIONAL demo on top of the catalog.

Idempotent and non-destructive: accounts, profiles and sample jobs are created
only when missing; nothing that already exists is changed (team data is safe).
`--reset-onboarding` is the one exception: it deletes the worker profile of the
two fresh onboarding accounts so the ID-scan flow can be shown again.

All accounts are demo-only and share one local password (default below,
override with --password or DEMO_PASSWORD). Refuses to run with DEBUG off.
"""

import os
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from catalog.models import ServiceArea, Specialty, Trade
from workers.identity import identity_digest, mask_cnic
from workers.models import ScanProof, WorkerProfile

from ...models import Booking, BookingStatus, JobRequest, Quote, Review

DEFAULT_PASSWORD = "RozgarDemo#2026"
TAG = "[demo]"

CUSTOMERS = ["demo_ayesha", "demo_bilal"]
FRESH_WORKERS = ["demo_imran", "demo_tariq"]  # mock OCR: card-5 (default) / card-6
STAFF = "demo_staff"

# username, display name, years, card digits (fictional registry), trades, specialties, areas
READY_WORKERS = [
    ("demo_akram", "Akram Electric Works", 8, "0000000000011",
     ["electrical"], ["wiring", "fan-installation"], ["G-11", "G-13"]),
    ("demo_naveed", "Naveed AC & Cooling", 6, "0000000000022",
     ["ac-repair", "electrical"], ["ac-service", "gas-refill", "ups-inverter"], ["G-11", "I-10"]),
    ("demo_rashid", "Rashid Plumbing Services", 12, "0000000000033",
     ["plumbing"], ["leak-repair", "drain-blockage"], ["G-11", "G-13", "I-10"]),
    ("demo_sajid", "Sajid Woodworks", 15, "0000000000044",
     ["carpentry"], ["furniture-repair", "door-window"], ["G-13", "F-10"]),
]
REGISTRY_NAMES = {"0000000000011": "Akram Khan", "0000000000022": "Naveed Iqbal",
                  "0000000000033": "Rashid Mehmood", "0000000000044": "Sajid Hussain"}

# Completed history so ratings and job counts come from real records.
# worker, customer, trade, specialty, area, description, amount, rating, review text, tags
HISTORY = [
    ("demo_akram", "demo_bilal", "electrical", "wiring", "G-11", "Kitchen socket sparking", "1800", 5,
     "Came on time and explained the fault.", ["on_time", "quality_work"]),
    ("demo_akram", "demo_bilal", "electrical", "fan-installation", "G-13", "Install two ceiling fans", "2500", 4,
     "Good work, slightly late.", ["quality_work", "fair_price"]),
    ("demo_rashid", "demo_bilal", "plumbing", "leak-repair", "G-13", "Bathroom tap leaking", "1200", 5,
     "", ["fair_price", "clean_work"]),
    ("demo_naveed", "demo_bilal", "ac-repair", "ac-service", "I-10", "AC service before summer", "3000", 4,
     "Cleaned both units properly.", ["polite"]),
]
OPEN_REQUESTS = [
    ("demo_bilal", "carpentry", "door-window", "G-13", "Wardrobe door hinge broken, door hangs loose"),
]


class Command(BaseCommand):
    help = "Seed fictional demo accounts, worker profiles and sample jobs (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=os.environ.get("DEMO_PASSWORD", DEFAULT_PASSWORD))
        parser.add_argument("--reset-onboarding", action="store_true",
                            help="Delete the fresh onboarding accounts' profiles so the scan can be demoed again.")
        parser.add_argument("--force", action="store_true", help="Allow running with DEBUG off.")

    def handle(self, *args, password, reset_onboarding, force, **options):
        if not settings.DEBUG and not force:
            raise CommandError("seed_demo creates demo accounts with a shared password; run only with DEBUG on "
                               "(or pass --force for a throwaway environment).")
        call_command("seed_catalog", stdout=self.stdout)
        self.created = []
        with transaction.atomic():
            users = {}
            for name in CUSTOMERS:
                users[name] = self._user(name, "customer", password)
            for name in FRESH_WORKERS:
                users[name] = self._user(name, "worker", password)
            for row in READY_WORKERS:
                users[row[0]] = self._user(row[0], "worker", password)
                self._profile(users[row[0]], *row[1:])
            self._user(STAFF, "customer", password, is_staff=True, is_superuser=True)
            for row in HISTORY:
                self._history(users, *row)
            for row in OPEN_REQUESTS:
                self._open_request(users, *row)
            if reset_onboarding:
                n, _ = WorkerProfile.objects.filter(user__username__in=FRESH_WORKERS).delete()
                ScanProof.objects.filter(user__username__in=FRESH_WORKERS).delete()
                self.stdout.write(f"reset onboarding for {', '.join(FRESH_WORKERS)} ({n} profile rows removed)")
        self.stdout.write(f"created: {', '.join(self.created) or 'nothing (already seeded)'}")
        self.stdout.write(self.style.SUCCESS("Demo seed complete. All data is fictional and demo-only."))

    def _user(self, username, role, password, **flags):
        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.create_user(username, password=password, role=role, **flags)
            self.created.append(username)
        return user

    def _profile(self, user, display_name, years, digits, trades, specialties, areas):
        if WorkerProfile.objects.filter(user=user).exists():
            return
        if WorkerProfile.objects.filter(identity_digest=identity_digest(digits)).exists():
            self.stdout.write(self.style.WARNING(f"skip profile for {user.username}: fictional ID already linked"))
            return
        profile = WorkerProfile.objects.create(
            user=user, display_name=display_name, experience_years=years, accepting_jobs=True,
            verified_name=REGISTRY_NAMES[digits], id_masked=mask_cnic(digits),
            identity_digest=identity_digest(digits), identity_simulated=True, verified_at=timezone.now(),
        )
        profile.trades.set(Trade.objects.filter(slug__in=trades))
        profile.specialties.set(Specialty.objects.filter(trade__slug__in=trades, slug__in=specialties))
        profile.service_areas.set(ServiceArea.objects.filter(city="Islamabad", sector_code__in=areas))
        self.created.append(f"profile:{user.username}")

    def _job(self, users, customer, trade, specialty, area, description):
        text = f"{TAG} {description}"
        job = JobRequest.objects.filter(customer=users[customer], description=text).first()
        if job is not None:
            return job, False
        trade_obj = Trade.objects.get(slug=trade)
        return JobRequest.objects.create(
            customer=users[customer], trade=trade_obj, description=text,
            specialty=Specialty.objects.filter(trade=trade_obj, slug=specialty).first(),
            service_area=ServiceArea.objects.get(city="Islamabad", sector_code=area),
            address_details="Demo address - fictional",
        ), True

    def _history(self, users, worker, customer, trade, specialty, area, description, amount, rating, text, tags):
        job, created = self._job(users, customer, trade, specialty, area, description)
        if not created:
            return
        quote = Quote.objects.create(job=job, worker=users[worker], amount=Decimal(amount), message="Demo quote")
        done = timezone.now() - timedelta(days=len(self.created) + 3)
        booking = Booking.objects.create(
            job=job, quote=quote, worker=users[worker], customer=users[customer], amount=quote.amount,
            status=BookingStatus.COMPLETED, checked_in_at=done - timedelta(hours=2), completed_at=done,
        )
        Review.objects.create(booking=booking, customer=users[customer], worker=users[worker],
                              rating=rating, text=text, tags=tags)
        self.created.append(f"history:{worker}")

    def _open_request(self, users, customer, trade, specialty, area, description):
        _, created = self._job(users, customer, trade, specialty, area, description)
        if created:
            self.created.append(f"open-request:{trade}")
