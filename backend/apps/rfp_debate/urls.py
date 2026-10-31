from django.urls import path

from .views import RFPCardsSnapshotView, RFPDetailView, RFPListCreateView, RFPStartDebateView

urlpatterns = [
    path("", RFPListCreateView.as_view()),
    path("<uuid:pk>/", RFPDetailView.as_view()),
    path("<uuid:pk>/cards/", RFPCardsSnapshotView.as_view()),
    path("<uuid:pk>/start-debate/", RFPStartDebateView.as_view()),
]
