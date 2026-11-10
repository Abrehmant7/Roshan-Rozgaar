from django.urls import path

from . import views

urlpatterns = [
    path("workers/", views.WorkerDiscoveryView.as_view(), name="worker-discovery"),
    path("job-requests/", views.JobRequestListCreateView.as_view(), name="job-requests"),
    path("job-requests/<int:pk>/", views.JobRequestDetailView.as_view(), name="job-request-detail"),
    path("job-requests/<int:pk>/voice-note/", views.VoiceNoteView.as_view(), name="job-request-voice-note"),
    path("job-board/", views.JobBoardView.as_view(), name="job-board"),
]
