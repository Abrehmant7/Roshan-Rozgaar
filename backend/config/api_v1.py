"""Routes mounted under /api/v1/. Feature apps add their URLconfs here."""

from django.urls import include, path

from .views import HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("auth/", include("accounts.urls")),
    path("catalog/", include("catalog.urls")),
    path("", include("workers.urls")),
]
