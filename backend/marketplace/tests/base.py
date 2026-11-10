import shutil
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from catalog.models import ServiceArea, Specialty, Trade
from config.testing import WEBM, Session, make_user, make_worker, upload

JOBS = "/api/v1/job-requests/"
BOARD = "/api/v1/job-board/"
DISCOVER = "/api/v1/workers/"


class MarketplaceTestCase(TestCase):
    """Seeded catalog, two customers and workers in different trades/areas."""

    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.mkdtemp(prefix="rr-private-")
        cls._media_override = override_settings(PRIVATE_MEDIA_ROOT=cls._media)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        shutil.rmtree(cls._media, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command("seed_catalog", stdout=StringIO())
        cls.electrical = Trade.objects.get(slug="electrical")
        cls.plumbing = Trade.objects.get(slug="plumbing")
        cls.carpentry = Trade.objects.get(slug="carpentry")
        cls.wiring = Specialty.objects.get(trade=cls.electrical, slug="wiring")
        cls.fan = Specialty.objects.get(trade=cls.electrical, slug="fan-installation")
        cls.leak = Specialty.objects.get(trade=cls.plumbing, slug="leak-repair")
        cls.g11 = ServiceArea.objects.get(sector_code="G-11")
        cls.g13 = ServiceArea.objects.get(sector_code="G-13")
        cls.i10 = ServiceArea.objects.get(sector_code="I-10")

        cls.ayesha = make_user("ayesha")
        cls.bilal = make_user("bilal")
        # electrician in G-11 with the wiring specialty
        cls.akram = make_worker("akram", [cls.electrical], [cls.g11], [cls.wiring], name="Akram")
        # electrician generalist in G-11 and G-13
        cls.naveed = make_worker("naveed", [cls.electrical], [cls.g11, cls.g13], name="Naveed")
        # electrician who only covers I-10
        cls.rashid = make_worker("rashid", [cls.electrical], [cls.i10], name="Rashid")
        # plumber in G-11
        cls.sajid = make_worker("sajid", [cls.plumbing], [cls.g11], [cls.leak], name="Sajid")
        # worker account with no profile yet
        cls.newbie = make_user("newbie", role="worker")

    def session(self, user):
        return Session(user)

    def post_job(self, api, **fields):
        body = {"trade": self.electrical.id, "service_area": self.g11.id,
                "description": "Ceiling fan sparks when switched on", "address_details": "House 12, Street 4"}
        body.update(fields)
        voice = body.pop("voice", None)
        if voice is not None:
            body["voice_note"] = upload(*voice) if isinstance(voice, tuple) else upload("rec.webm", voice, "audio/webm")
            body = {k: v for k, v in body.items() if v is not None}
            return api.post(JOBS, body, multipart=True)
        return api.post(JOBS, body)

    WEBM = WEBM
