from django.conf import settings
from django.utils import timezone
from rest_framework import generics, parsers, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsDesignerRole
from apps.guardrails.validators import sanitize_template_html, sanitize_template_js

from .design_agent import DesignerStudioAgent
from .media_service import format_assets_for_agent, save_designer_asset
from .models import DesignerMediaAsset, ProposalTemplate, REQUIRED_PLACEHOLDERS
from .revisions import append_revision
from .serializers import DesignerMediaAssetSerializer, ProposalTemplateSerializer
from .services import compile_template, deterministic_template_checks
from .venue_map_context import (
    build_default_map_agent_context,
    default_map_designer_payload,
    inject_map_section_into_template,
)


class ProposalTemplateListCreateView(generics.ListCreateAPIView):
    serializer_class = ProposalTemplateSerializer

    def get_permissions(self):
        return [IsDesignerRole()]

    def get_queryset(self):
        return ProposalTemplate.objects.filter(designer=self.request.user).order_by("-updated_at")

    def perform_create(self, serializer):
        html = serializer.validated_data.get("html_markup", "")
        css = serializer.validated_data.get("css_stylesheet", "")
        js = serializer.validated_data.get("js_script", "")
        self._validate_before_save(html, css, js)
        clean_html = sanitize_template_html(html)
        clean_js = sanitize_template_js(js)
        instance = serializer.save(
            designer=self.request.user,
            html_markup=clean_html,
            js_script=clean_js,
            required_placeholders_json=REQUIRED_PLACEHOLDERS,
        )
        append_revision(instance, note="create")
        instance.save(update_fields=["revision_history_json"])

    @staticmethod
    def _validate_before_save(html: str, css: str, js: str = "") -> None:
        issues = deterministic_template_checks(html, css, js)
        if issues:
            raise DRFValidationError("; ".join(issues))
        agent = DesignerStudioAgent()
        review = agent.validate_layout(
            html_markup=html, css_stylesheet=css, js_script=js
        )
        if not review.get("valid"):
            raise DRFValidationError(
                review.get("summary") or "; ".join(review.get("issues") or [])
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
        js = serializer.validated_data.get("js_script", serializer.instance.js_script)
        ProposalTemplateListCreateView._validate_before_save(html, css, js)
        clean_html = sanitize_template_html(html)
        clean_js = sanitize_template_js(js)
        chat_history = serializer.validated_data.get(
            "chat_history_json", serializer.instance.chat_history_json
        )
        instance = serializer.save(
            html_markup=clean_html,
            js_script=clean_js,
            chat_history_json=chat_history,
        )
        append_revision(instance, note="update")
        instance.save(update_fields=["revision_history_json"])


class DesignerMediaUploadView(APIView):
    permission_classes = [IsDesignerRole]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file is required"}, status=status.HTTP_400_BAD_REQUEST)

        template = None
        template_id = request.data.get("template_id")
        if template_id:
            template = ProposalTemplate.objects.filter(
                pk=template_id, designer=request.user
            ).first()

        try:
            asset = save_designer_asset(
                designer=request.user,
                upload=upload,
                request=request,
                template=template,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            DesignerMediaAssetSerializer(asset, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class DesignerMediaListView(generics.ListAPIView):
    serializer_class = DesignerMediaAssetSerializer
    permission_classes = [IsDesignerRole]

    def get_queryset(self):
        qs = DesignerMediaAsset.objects.filter(designer=self.request.user).order_by(
            "-created_at"
        )
        template_id = self.request.query_params.get("template_id")
        if template_id:
            qs = qs.filter(template_id=template_id)
        return qs[:100]


class DesignerChatView(APIView):
    permission_classes = [IsDesignerRole]

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        attachment_ids = request.data.get("attachment_ids") or []
        if not message and not attachment_ids:
            return Response(
                {"detail": "message or attachments required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        history = request.data.get("history") or []
        html_markup = request.data.get("html_markup") or ""
        css_stylesheet = request.data.get("css_stylesheet") or ""
        js_script = request.data.get("js_script") or ""
        template_id = request.data.get("template_id")

        assets = list(
            DesignerMediaAsset.objects.filter(
                id__in=attachment_ids, designer=request.user
            )
        )
        attachment_block = format_assets_for_agent(assets)
        venue_map_block = build_default_map_agent_context()

        agent = DesignerStudioAgent()
        result = agent.chat_turn(
            message=message or "Use the attached media in the proposal design.",
            history=history,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            attachment_block=attachment_block,
            venue_map_block=venue_map_block,
        )

        display_message = message
        if assets:
            names = ", ".join(a.original_name for a in assets)
            display_message = f"{message}\n[Attachments: {names}]".strip()

        new_history = list(history)
        now = timezone.now().isoformat()
        if display_message:
            new_history.append(
                {"role": "user", "content": display_message, "ts": now}
            )
        new_history.append(
            {
                "role": "assistant",
                "content": result["assistant_message"],
                "ts": timezone.now().isoformat(),
            }
        )

        if template_id:
            template = ProposalTemplate.objects.filter(
                pk=template_id, designer=request.user
            ).first()
            if template:
                template.chat_history_json = new_history
                template.html_markup = result["html_markup"]
                template.css_stylesheet = result["css_stylesheet"]
                template.js_script = result.get("js_script", js_script)
                template.save(
                    update_fields=[
                        "chat_history_json",
                        "html_markup",
                        "css_stylesheet",
                        "js_script",
                        "updated_at",
                    ]
                )

        return Response(
            {
                **result,
                "history": new_history,
                "attachments": DesignerMediaAssetSerializer(
                    assets, many=True, context={"request": request}
                ).data,
                "used_fixture": bool(
                    settings.USE_FIXTURE_DEBATE or not settings.META_MODEL_API_KEY
                ),
            }
        )


class TemplateValidateView(APIView):
    permission_classes = [IsDesignerRole]

    def post(self, request):
        html = request.data.get("html_markup") or ""
        css = request.data.get("css_stylesheet") or ""
        js = request.data.get("js_script") or ""
        compiled = request.data.get("compiled_html") or compile_template(html, css, js_script=js)
        agent = DesignerStudioAgent()
        review = agent.validate_layout(
            html_markup=html,
            css_stylesheet=css,
            js_script=js,
            compiled_html=compiled,
        )
        return Response(review)


class TemplatePreviewView(APIView):
    permission_classes = [IsDesignerRole]

    def post(self, request):
        html = request.data.get("html_markup") or ""
        css = request.data.get("css_stylesheet") or ""
        js = request.data.get("js_script") or ""
        compiled = compile_template(html, css, js_script=js)
        return Response({"compiled_html": compiled})


class TemplateDuplicateView(APIView):
    permission_classes = [IsDesignerRole]

    def post(self, request, pk):
        source = ProposalTemplate.objects.filter(pk=pk, designer=request.user).first()
        if not source:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        copy = ProposalTemplate.objects.create(
            name=f"{source.name} (copy)",
            designer=request.user,
            html_markup=source.html_markup,
            css_stylesheet=source.css_stylesheet,
            js_script=source.js_script,
            required_placeholders_json=source.required_placeholders_json,
            chat_history_json=source.chat_history_json,
            is_default=False,
        )
        append_revision(copy, note="duplicate")
        copy.save(update_fields=["revision_history_json"])
        return Response(
            ProposalTemplateSerializer(copy, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class TemplateRestoreRevisionView(APIView):
    permission_classes = [IsDesignerRole]

    def post(self, request, pk):
        template = ProposalTemplate.objects.filter(pk=pk, designer=request.user).first()
        if not template:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        try:
            index = int(request.data.get("index", 0))
        except (TypeError, ValueError):
            return Response({"detail": "index required"}, status=status.HTTP_400_BAD_REQUEST)
        revisions = list(template.revision_history_json or [])
        if index < 0 or index >= len(revisions):
            return Response({"detail": "Invalid revision index"}, status=status.HTTP_400_BAD_REQUEST)
        rev = revisions[index]
        template.html_markup = rev.get("html_markup", template.html_markup)
        template.css_stylesheet = rev.get("css_stylesheet", template.css_stylesheet)
        template.js_script = rev.get("js_script", template.js_script)
        template.save(
            update_fields=["html_markup", "css_stylesheet", "js_script", "updated_at"]
        )
        return Response(
            ProposalTemplateSerializer(template, context={"request": request}).data
        )


class TemplateExportView(APIView):
    permission_classes = [IsDesignerRole]

    def get(self, request, pk):
        template = ProposalTemplate.objects.filter(pk=pk, designer=request.user).first()
        if not template:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "template": ProposalTemplateSerializer(
                    template, context={"request": request}
                ).data,
                "exported_at": timezone.now().isoformat(),
            }
        )


class DefaultTemplateView(generics.RetrieveAPIView):
    serializer_class = ProposalTemplateSerializer
    permission_classes = []

    def get_object(self):
        return ProposalTemplate.objects.filter(is_default=True).first()


class DesignerDefaultVenueMapView(APIView):
    """Read system default map for Designer Studio agents and toolbar."""

    permission_classes = [IsDesignerRole]

    def get(self, request):
        return Response(default_map_designer_payload())


class DesignerInjectDefaultMapView(APIView):
    """Insert venue-map section + slot CSS around {{selected_map_svg}}."""

    permission_classes = [IsDesignerRole]

    def post(self, request):
        html = request.data.get("html_markup") or ""
        css = request.data.get("css_stylesheet") or ""
        updated = inject_map_section_into_template(html, css)
        payload = default_map_designer_payload()
        return Response({**updated, "default_map": payload})
