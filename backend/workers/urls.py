from django.urls import path

from . import views

urlpatterns = [
    path("workers/me/", views.WorkerMeView.as_view(), name="worker-me"),
    path("workers/me/scan/", views.ScanView.as_view(), name="worker-scan"),
    path("workers/me/availability/", views.AvailabilityView.as_view(), name="worker-availability"),
]
