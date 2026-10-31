from django.urls import path

from .views import (
    AgentTagZoneView,
    VenueMapListCreateView,
    VenueMapVectorizeView,
    VenueMapVerifyView,
    VenueMapZoneUpdateView,
)

urlpatterns = [
    path("", VenueMapListCreateView.as_view()),
    path("<uuid:pk>/vectorize/", VenueMapVectorizeView.as_view()),
    path("<uuid:pk>/verify/", VenueMapVerifyView.as_view()),
    path("zones/<uuid:pk>/", VenueMapZoneUpdateView.as_view()),
    path("agent/tag-zone/", AgentTagZoneView.as_view()),
]
