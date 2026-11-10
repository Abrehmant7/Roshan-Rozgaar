from django.apps import AppConfig


class WorkersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "workers"

    def ready(self):
        from django.core import checks

        @checks.register(checks.Tags.compatibility)
        def ocr_configuration(app_configs, **kwargs):
            from django.conf import settings

            if settings.OCR_MODE == "live" and not settings.OCR_API_KEY:
                return [checks.Warning(
                    "OCR_MODE=live but OCR_API_KEY is empty; ID scans will answer 503 ocr_not_configured.",
                    hint="Set OCR_API_KEY in the root .env (never commit it), or use OCR_MODE=mock.",
                    id="workers.W001",
                )]
            return []
