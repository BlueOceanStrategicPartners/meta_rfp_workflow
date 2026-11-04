from django.urls import path

from .views import (
    RFPCardsSnapshotView,
    RFPArchiveView,
    RFPDetailView,
    RFPListCreateView,
    RFPSessionSummariesView,
    RFPStartDebateView,
)

urlpatterns = [
    path("sessions/", RFPSessionSummariesView.as_view()),
    path("", RFPListCreateView.as_view()),
    path("<uuid:pk>/archive/", RFPArchiveView.as_view()),
    path("<uuid:pk>/", RFPDetailView.as_view()),
    path("<uuid:pk>/cards/", RFPCardsSnapshotView.as_view()),
    path("<uuid:pk>/start-debate/", RFPStartDebateView.as_view()),
]
