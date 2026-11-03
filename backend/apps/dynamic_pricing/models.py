import uuid

from django.conf import settings
from django.db import models

from apps.designer_studio.models import ProposalTemplate
from apps.rfp_debate.models import RFPSubmission

DEFAULT_SEASONALITY = {"6": 1.15, "7": 1.15, "11": 1.15, "12": 1.15}


class PricingPolicy(models.Model):
    """Admin-editable pricing rules (singleton, pk=1). Env settings seed the first row."""

    walk_away_floor_margin_pct = models.FloatField(default=0.12)
    max_autonomous_discount_pct = models.FloatField(default=0.15)
    target_markup_pct = models.FloatField(default=0.18)
    anchor_markup_pct = models.FloatField(default=0.08)
    event_multiplier = models.FloatField(default=1.0)
    seasonality_json = models.JSONField(default=dict)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls) -> "PricingPolicy":
        policy, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                "walk_away_floor_margin_pct": settings.WALK_AWAY_FLOOR_MARGIN_PCT,
                "max_autonomous_discount_pct": settings.MAX_AUTONOMOUS_DISCOUNT_PCT,
                "seasonality_json": dict(DEFAULT_SEASONALITY),
            },
        )
        return policy

    def season(self, month: int | None) -> float:
        if not month:
            return 1.0
        return float((self.seasonality_json or {}).get(str(month), 1.0))


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
