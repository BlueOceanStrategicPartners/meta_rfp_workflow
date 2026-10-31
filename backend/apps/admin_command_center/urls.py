from django.urls import path

from .views import (
    DebateObservatoryView,
    HumanOverrideDebateView,
    ModuleStubView,
    NegotiationMonitorView,
    OccupancyIngestView,
    SLATelemetryView,
)

urlpatterns = [
    path("modules/", ModuleStubView.as_view()),
    path("debate-observatory/", DebateObservatoryView.as_view()),
    path("sla/", SLATelemetryView.as_view()),
    path("negotiations/", NegotiationMonitorView.as_view()),
    path("occupancy/ingest/", OccupancyIngestView.as_view()),
    path("debate/<uuid:rfp_id>/override/", HumanOverrideDebateView.as_view()),
]
