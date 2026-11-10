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
]
