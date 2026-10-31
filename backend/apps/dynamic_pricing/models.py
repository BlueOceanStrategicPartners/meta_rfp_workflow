import uuid

from django.db import models

from apps.designer_studio.models import ProposalTemplate
from apps.rfp_debate.models import RFPSubmission


class DynamicPricingQuote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfp = models.ForeignKey(
        RFPSubmission, on_delete=models.CASCADE, related_name="pricing_quotes"
    )
    xgboost_demand_score = models.FloatField(default=0.0)
    walk_away_floor_price = models.DecimalField(max_digits=14, decimal_places=2)
    optimal_target_price = models.DecimalField(max_digits=14, decimal_places=2)
    initial_anchor_price = models.DecimalField(max_digits=14, decimal_places=2)
    shap_explanations_json = models.JSONField(default=dict)
    agreed_final_price = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    used_fallback_engine = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class RenderedProposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfp = models.OneToOneField(
        RFPSubmission, on_delete=models.CASCADE, related_name="rendered_proposal"
    )
    template = models.ForeignKey(
        ProposalTemplate, on_delete=models.SET_NULL, null=True, related_name="rendered_proposals"
    )
    compiled_proposal_html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
