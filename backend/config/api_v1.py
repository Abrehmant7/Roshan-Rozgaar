"""Routes mounted under /api/v1/. Feature apps add their URLconfs here."""

from django.urls import path

from .views import HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
]
