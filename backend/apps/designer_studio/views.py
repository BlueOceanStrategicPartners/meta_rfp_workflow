from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsAdminRole, IsDesignerRole
from apps.core.exceptions import TemplateValidationException
from apps.guardrails.validators import lint_required_placeholders, sanitize_template_html

from .models import ProposalTemplate, REQUIRED_PLACEHOLDERS
from .serializers import ProposalTemplateSerializer


class ProposalTemplateListCreateView(generics.ListCreateAPIView):
    serializer_class = ProposalTemplateSerializer

    def get_permissions(self):
        return [IsDesignerRole()]

    def get_queryset(self):
        return ProposalTemplate.objects.filter(designer=self.request.user)

    def perform_create(self, serializer):
        html = serializer.validated_data.get("html_markup", "")
        css = serializer.validated_data.get("css_stylesheet", "")
        lint_required_placeholders(html, css)
        clean_html = sanitize_template_html(html)
        serializer.save(
            designer=self.request.user,
            html_markup=clean_html,
            required_placeholders_json=REQUIRED_PLACEHOLDERS,
        )


class ProposalTemplateDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProposalTemplateSerializer

    def get_permissions(self):
        return [IsDesignerRole()]

    def get_queryset(self):
        return ProposalTemplate.objects.filter(designer=self.request.user)

    def perform_update(self, serializer):
        html = serializer.validated_data.get("html_markup", serializer.instance.html_markup)
        css = serializer.validated_data.get(
            "css_stylesheet", serializer.instance.css_stylesheet
        )
        is_default = serializer.validated_data.get("is_default", serializer.instance.is_default)
        if is_default:
            lint_required_placeholders(html, css)
        clean_html = sanitize_template_html(html)
        serializer.save(html_markup=clean_html)


class DesignerChatStubView(APIView):
    permission_classes = [IsDesignerRole]

    def post(self, request):
        instruction = request.data.get("instruction", "")
        sample_html = (
            "<section><h1>{{client_name}}</h1>"
            "<p>{{event_dates}}</p>"
            "{{verified_room_blocks}}"
            "{{selected_map_svg}}"
            "{{meeting_space_specs}}"
            "{{xgboost_quote_breakdown}}"
            "{{negotiated_concessions}}"
            "{{cta_accept_button}}</section>"
        )
        return Response({"html_markup": sample_html, "css_stylesheet": "body{font-family:sans-serif;}"})


class DefaultTemplateView(generics.RetrieveAPIView):
    serializer_class = ProposalTemplateSerializer
    permission_classes = []

    def get_object(self):
        return ProposalTemplate.objects.filter(is_default=True).first()
