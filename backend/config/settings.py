"""Django settings for the Roshan Rozgar backend.

All deployment-specific values come from environment variables. For local
development the repo-root `.env` is loaded first; variables already present
in the process environment take precedence over it.
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .env import env_bool, env_int, env_list, env_str, load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/
REPO_ROOT = BASE_DIR.parent

load_dotenv(REPO_ROOT / ".env")

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS")
# Origins allowed to send unsafe requests, e.g. the Vite dev server
# (http://localhost:5173) when it proxies /api to Django.
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# Session + CSRF cookies. The React client never reads the session cookie
# (HttpOnly); it gets the CSRF token from GET /api/v1/auth/csrf/.
# Secure cookies stay off for local HTTP; set DJANGO_SECURE_COOKIES=true
# when the site is served over HTTPS.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env_bool("DJANGO_SECURE_COOKIES", default=False)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_FAILURE_VIEW = "config.views.csrf_failure"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "catalog",
    "workers",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_str("DB_NAME"),
        "USER": env_str("DB_USER"),
        "PASSWORD": env_str("DB_PASSWORD"),
        "HOST": env_str("DB_HOST", "127.0.0.1"),
        "PORT": env_str("DB_PORT", "5432"),
        # Fail fast (e.g. for the health check) instead of hanging on a dead host.
        "OPTIONS": {"connect_timeout": 5},
    }
}

AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Karachi"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        *(["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    ],
    "EXCEPTION_HANDLER": "config.api.exception_handler",
    "DEFAULT_THROTTLE_RATES": {
        "ocr_scan": env_str("OCR_SCAN_RATE", "30/hour"),
    },
}

# Uploads that must never be publicly served (voice notes). Served only through
# authorized API views; keep this directory out of Git and outside MEDIA_ROOT.
PRIVATE_MEDIA_ROOT = Path(env_str("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media")))

# ID-card OCR for worker onboarding. "mock" uses built-in fictional fixtures;
# "live" calls the configured provider from the server (the key never reaches React).
OCR_MODE = env_str("OCR_MODE", "mock").strip().lower()
if OCR_MODE not in {"mock", "live"}:
    raise ImproperlyConfigured("OCR_MODE must be 'mock' or 'live'.")
OCR_ENDPOINT = env_str("OCR_ENDPOINT", "")
OCR_API_KEY = env_str("OCR_API_KEY", "")
OCR_API_KEY_HEADER = env_str("OCR_API_KEY_HEADER", "X-API-Key")
OCR_IMAGE_FIELD = env_str("OCR_IMAGE_FIELD", "image")
OCR_TEXT_FIELD = env_str("OCR_TEXT_FIELD", "text")
OCR_TIMEOUT_SECONDS = env_int("OCR_TIMEOUT_SECONDS", 10)
OCR_MAX_IMAGE_BYTES = env_int("OCR_MAX_IMAGE_BYTES", 5 * 1024 * 1024)
if OCR_MODE == "live" and not OCR_ENDPOINT:
    raise ImproperlyConfigured("OCR_MODE=live requires OCR_ENDPOINT.")
SCAN_PROOF_TTL_SECONDS = env_int("SCAN_PROOF_TTL_SECONDS", 10 * 60)
