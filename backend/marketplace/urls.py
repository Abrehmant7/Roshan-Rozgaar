from django.urls import path

from . import views

urlpatterns = [
    path("workers/", views.WorkerDiscoveryView.as_view(), name="worker-discovery"),
    path("job-requests/", views.JobRequestListCreateView.as_view(), name="job-requests"),
    path("job-requests/<int:pk>/", views.JobRequestDetailView.as_view(), name="job-request-detail"),
    path("job-requests/<int:pk>/voice-note/", views.VoiceNoteView.as_view(), name="job-request-voice-note"),
    path("job-board/", views.JobBoardView.as_view(), name="job-board"),
    path("job-requests/<int:pk>/quotes/", views.JobQuotesView.as_view(), name="job-request-quotes"),
    path("quotes/", views.MyQuotesView.as_view(), name="my-quotes"),
    path("quotes/<int:pk>/accept/", views.AcceptQuoteView.as_view(), name="quote-accept"),
    path("bookings/", views.BookingListView.as_view(), name="bookings"),
    path("bookings/<int:pk>/", views.BookingDetailView.as_view(), name="booking-detail"),
    path("bookings/<int:pk>/pin/", views.IssuePinView.as_view(), name="booking-pin"),
    path("bookings/<int:pk>/check-in/", views.CheckInView.as_view(), name="booking-check-in"),
    path("bookings/<int:pk>/complete/", views.CompleteView.as_view(), name="booking-complete"),
    path("bookings/<int:pk>/review/", views.ReviewCreateView.as_view(), name="booking-review"),
    path("bookings/<int:pk>/reports/", views.ReportCreateView.as_view(), name="booking-reports"),
    path("reports/", views.MyReportsView.as_view(), name="my-reports"),
    path("reports/reasons/", views.ReportReasonsView.as_view(), name="report-reasons"),
    path("reviews/tags/", views.ReviewTagsView.as_view(), name="review-tags"),
    path("workers/me/dashboard/", views.WorkerDashboardView.as_view(), name="worker-dashboard"),
    path("workers/<int:pk>/", views.WorkerPublicView.as_view(), name="worker-public"),
]
