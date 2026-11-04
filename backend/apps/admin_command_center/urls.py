from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    AuditListView,
    DebateObservatoryView,
    ModuleStubView,
    NegotiationConversationView,
    NegotiationListView,
    NegotiationMessageView,
    NegotiationReleaseView,
    NegotiationTakeoverView,
    OccupancyIngestView,
    OccupancyListView,
    OccupancySummaryView,
    OccupancyUploadView,
    OverviewView,
    PricingModelView,
    PricingPolicyView,
    PricingQuotesView,
    PricingRetrainView,
    QuoteExplanationView,
    PropertyViewSet,
    RFPDetailView,
    RFPListView,
    RFPOverrideView,
    SLATelemetryView,
    SpaceViewSet,
    TelemetryView,
)

# SimpleRouter (not DefaultRouter): no browsable API root that would bypass IsAdminRole.
router = SimpleRouter()
router.register("inventory/properties", PropertyViewSet, basename="admin-property")
router.register("inventory/spaces", SpaceViewSet, basename="admin-space")

urlpatterns = [
    path("overview/", OverviewView.as_view()),
    path("telemetry/", TelemetryView.as_view()),
    path("audit/", AuditListView.as_view()),
    # Module 2 — debate observatory
    path("rfps/", RFPListView.as_view()),
    path("rfps/<uuid:pk>/", RFPDetailView.as_view()),
    path("rfps/<uuid:pk>/override/", RFPOverrideView.as_view()),
    path("debate/<uuid:pk>/override/", RFPOverrideView.as_view()),  # original path, kept as alias
    path("debate-observatory/", DebateObservatoryView.as_view()),
    # Module 3 — pricing
    path("pricing/policy/", PricingPolicyView.as_view()),
    path("pricing/model/", PricingModelView.as_view()),
    path("pricing/retrain/", PricingRetrainView.as_view()),
    path("pricing/quotes/", PricingQuotesView.as_view()),
    path("pricing/quotes/<uuid:pk>/explanation/", QuoteExplanationView.as_view()),
    # Module 4 — negotiations
    path("negotiations/", NegotiationListView.as_view()),
    path("negotiations/<uuid:pk>/takeover/", NegotiationTakeoverView.as_view()),
    path("negotiations/<uuid:pk>/release/", NegotiationReleaseView.as_view()),
    path("negotiations/<uuid:pk>/message/", NegotiationMessageView.as_view()),
    path("negotiations/<uuid:pk>/conversation/", NegotiationConversationView.as_view()),
    # Module 6 — occupancy
    path("occupancy/", OccupancyListView.as_view()),
    path("occupancy/upload/", OccupancyUploadView.as_view()),
    path("occupancy/summary/", OccupancySummaryView.as_view()),
    path("occupancy/ingest/", OccupancyIngestView.as_view()),
    # Module 7 — telemetry (original endpoints kept)
    path("sla/", SLATelemetryView.as_view()),
    path("modules/", ModuleStubView.as_view()),
    *router.urls,  # Module 5 — inventory
]
