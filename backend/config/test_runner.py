"""Test runner that never calls the live OCR provider.

The local .env may select OCR_MODE=live with a real key; tests always run against
the mock (tests that exercise the live adapter fake the network explicitly).
"""

from django.conf import settings
from django.test.runner import DiscoverRunner


class OfflineOcrRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        settings.OCR_MODE = "mock"
        settings.OCR_API_KEY = ""
