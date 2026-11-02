import logging

from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework import generics, parsers, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsDesignerRole
from apps.core.renderers import ServerSentEventsRenderer
from apps.guardrails.validators import sanitize_template_html, sanitize_template_js

from .designer_chat_service import iter_designer_chat, run_designer_chat_sync, sse_line, sse_preamble
from .designer_live_progress import get_live_progress
from .design_agent import DesignerStudioAgent
from .media_service import save_designer_asset
from .models import DesignerMediaAsset, ProposalTemplate, REQUIRED_PLACEHOLDERS
from .revisions import append_revision
from .serializers import DesignerMediaAssetSerializer, ProposalTemplateSerializer
from .services import compile_template, deterministic_template_checks
from .venue_map_context import (
    default_map_designer_payload,
    inject_map_section_into_template,
    remove_map_slot_from_template,
)

logger = logging.getLogger(__name__)


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
        html, css, js = self._prepare_for_save(html, css, js)
        clean_html = sanitize_template_html(html)
        clean_js = sanitize_template_js(js)
        instance = serializer.save(
            designer=self.request.user,
            html_markup=clean_html,
            css_stylesheet=css,
            js_script=clean_js,
            required_placeholders_json=REQUIRED_PLACEHOLDERS,
        )
        append_revision(instance, note="create")
        instance.save(update_fields=["revision_history_json"])

    @staticmethod
    def _prepare_for_save(html: str, css: str, js: str = "") -> tuple[str, str, str]:
        agent = DesignerStudioAgent()
        try:
            prepared = agent.prepare_for_save(html, css, js)
        except ValueError as exc:
            raise DRFValidationError(str(exc)) from exc
        return (
            prepared.get("html_markup") or html,
            prepared.get("css_stylesheet") or css,
            prepared.get("js_script") or js,
        )

    @staticmethod
    def _validate_before_save(html: str, css: str, js: str = "") -> None:
        """Legacy gate — prefer _prepare_for_save (auto-repair loop)."""
        issues = deterministic_template_checks(html, css, js)
        if issues:
            raise DRFValidationError("; ".join(issues))
        agent = DesignerStudioAgent()
        review = agent.validate_layout_for_save(
            html_markup=html, css_stylesheet=css, js_script=js
        )
        if not review.get("valid"):
            blockers = review.get("issues") or []
            raise DRFValidationError(
                "; ".join(blockers) if blockers else review.get("summary") or "Template needs fixes."
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
        html, css, js = ProposalTemplateListCreateView._prepare_for_save(html, css, js)
        clean_html = sanitize_template_html(html)
        clean_js = sanitize_template_js(js)
        chat_history = serializer.validated_data.get(
            "chat_history_json", serializer.instance.chat_history_json
        )
        instance = serializer.save(
            html_markup=clean_html,
            css_stylesheet=css,
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
        try:
            payload = run_designer_chat_sync(user=request.user, data=request.data, request=request)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(payload)


class DesignerChatStreamView(APIView):
    permission_classes = [IsDesignerRole]
    renderer_classes = [ServerSentEventsRenderer]

    def perform_content_negotiation(self, request, force=False):
        return (ServerSentEventsRenderer(), "text/event-stream")

    def post(self, request):
        message = (request.data.get("message") or "").strip()
        attachment_ids = request.data.get("attachment_ids") or []
        if not message and not attachment_ids:
            return Response(
                {"detail": "message or attachments required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "Designer chat stream POST user=%s attachments=%s",
            getattr(request.user, "pk", None),
            len(attachment_ids),
        )

        chat_data = request.data
        chat_user = request.user

        def iter_sse_chunks():
            yield sse_preamble()
            try:
                for event, payload in iter_designer_chat(
                    user=chat_user, data=chat_data, request=request
                ):
                    yield sse_line(event, payload)
            except ValueError as exc:
                yield sse_line("error", {"message": str(exc)})
            except Exception as exc:  # pragma: no cover
                logger.exception("Designer chat stream failed")
                yield sse_line("error", {"message": str(exc)})

        response = StreamingHttpResponse(
            iter_sse_chunks(),
            content_type="text/event-stream; charset=utf-8",
        )
        response["Cache-Control"] = "no-cache, no-transform"
        response["Connection"] = "keep-alive"
        response["X-Accel-Buffering"] = "no"
        return response


class DesignerChatLiveProgressView(APIView):
    permission_classes = [IsDesignerRole]

    def get(self, request):
        payload = get_live_progress(user_id=request.user.pk)
        return Response(payload)


class DesignerPreviewAuditView(APIView):
    permission_classes = [IsDesignerRole]

    def post(self, request):
        from .preview_audit import audit_compiled_proposal_preview

        html = request.data.get("html_markup") or ""
        css = request.data.get("css_stylesheet") or ""
        js = request.data.get("js_script") or ""
        findings = audit_compiled_proposal_preview(html, css, js)
        return Response(
            {
                "findings": [
                    {"code": f.code, "message": f.message, "severity": f.severity}
                    for f in findings
                ]
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


class DesignerRemoveVenueMapSlotView(APIView):
    """Remove venue map section from proposal HTML (saved map library unchanged)."""

    permission_classes = [IsDesignerRole]

    def post(self, request):
        html = request.data.get("html_markup") or ""
        css = request.data.get("css_stylesheet") or ""
        return Response(
            {
                "html_markup": remove_map_slot_from_template(html),
                "css_stylesheet": css,
            }
        )
