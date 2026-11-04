from decimal import Decimal

from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsAdminRole
from apps.guardrails.validators import enforce_floor_price, validate_negotiation_text
from apps.rfp_debate.models import RFPSubmission

from .models import DynamicPricingQuote
from .services import compute_dynamic_quote, train_and_save_model


class AdminPricingGuardrailView(APIView):
    permission_classes = [IsAdminRole]

    def get(self, request):
        from .models import PricingPolicy

        policy = PricingPolicy.get_solo()
        return Response(
            {
                "walk_away_floor_margin_pct": policy.walk_away_floor_margin_pct,
                "max_autonomous_discount_pct": policy.max_autonomous_discount_pct,
            }
        )


class AdminPricingRetrainView(APIView):
    permission_classes = [IsAdminRole]

    def post(self, request):
        from apps.inventory.models import VenueProperty

        prop = VenueProperty.objects.first()
        if not prop:
            return Response({"status": "no_property"}, status=400)
        path = train_and_save_model(prop.id)
        return Response({"status": "ok", "artifact": path})


class QuoteDetailView(APIView):
    def get(self, request, rfp_id):
        from apps.accounts_rbac.models import UserRole

        from .services import client_quote_card

        quote = DynamicPricingQuote.objects.filter(rfp_id=rfp_id).order_by("-created_at").first()
        if not quote:
            return Response({"detail": "No quote"}, status=404)
        if getattr(request.user, "role", None) != UserRole.ADMIN:
            # Floor and target are internal; clients and designers see the opening offer only.
            return Response(client_quote_card(quote))
        return Response(
            {
                "walk_away_floor_price": str(quote.walk_away_floor_price),
                "optimal_target_price": str(quote.optimal_target_price),
                "initial_anchor_price": str(quote.initial_anchor_price),
                "shap": quote.explanation_json or quote.shap_explanations_json,
                "used_fallback": quote.used_fallback_engine,
                "engine": quote.engine,
                "model_version": quote.model_version,
                "fallback_reason": quote.fallback_reason,
            }
        )


class RenderProposalView(APIView):
    def post(self, request, rfp_id):
        from apps.designer_studio.models import ProposalTemplate
        from apps.dynamic_pricing.models import RenderedProposal

        rfp = RFPSubmission.objects.get(pk=rfp_id)
        template = ProposalTemplate.objects.filter(is_default=True).first()
        if not template:
            return Response({"detail": "No default template"}, status=400)
        quote = DynamicPricingQuote.objects.filter(rfp=rfp).order_by("-created_at").first()
        cards = rfp.active_ui_cards_json or {}
        from apps.designer_studio.services import compile_template
        compiled = compile_template(
            template.html_markup,
            template.css_stylesheet,
            js_script=template.js_script,
            cards=cards,
            quote=quote,
            use_seed_if_empty=False,
        )
        rendered = RenderedProposal.objects.update_or_create(
            rfp=rfp,
            defaults={"template": template, "compiled_proposal_html": compiled},
        )[0]
        from apps.rfp_debate.models import RFPStatus

        rfp.status = RFPStatus.PROPOSAL_RENDERED
        rfp.save(update_fields=["status"])
        return Response({"html": rendered.compiled_proposal_html})
