from django.urls import path

from .views import (
    AdminPricingGuardrailView,
    AdminPricingRetrainView,
    QuoteDetailView,
    RenderProposalView,
)

urlpatterns = [
    path("admin/guardrails/", AdminPricingGuardrailView.as_view()),
    path("admin/retrain/", AdminPricingRetrainView.as_view()),
    path("quote/<uuid:rfp_id>/", QuoteDetailView.as_view()),
    path("render/<uuid:rfp_id>/", RenderProposalView.as_view()),
]
