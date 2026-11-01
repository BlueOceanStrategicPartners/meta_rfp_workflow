from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from rest_framework import generics, parsers, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts_rbac.permissions import IsDesignerOrAdminRole
from apps.designer_studio.media_service import format_assets_for_agent, save_designer_asset
from apps.designer_studio.models import DesignerMediaAsset
from apps.designer_studio.serializers import DesignerMediaAssetSerializer
from apps.guardrails.validators import sanitize_template_html, sanitize_template_js
from apps.inventory.models import InteractiveVenueMap, VenueMapZone, VenueProperty

from .map_agent import MapStudioAgent
from .map_revisions import append_map_revision
from .map_services import (
    compile_interactive_map,
    sync_locations_to_zones,
    zone_detail_bundle,
)
from .pipeline import vectorize_map
from .serializers import VenueMapSerializer, VenueMapZoneSerializer
from apps.core.exceptions import MapVectorizationFallbackHandler


def _default_property() -> VenueProperty:
    prop, _ = VenueProperty.objects.get_or_create(name="Meta Grand Hotel")
    return prop


def _map_queryset_for_user(user):
    qs = InteractiveVenueMap.objects.all().order_by("-updated_at")
    if user.role == "ADMIN":
        return qs
    return qs.filter(created_by=user)


class VenueMapListCreateView(generics.ListCreateAPIView):
    serializer_class = VenueMapSerializer
    permission_classes = [IsDesignerOrAdminRole]

    def get_queryset(self):
        return _map_queryset_for_user(self.request.user).prefetch_related("zones")

    def perform_create(self, serializer):
        prop = serializer.validated_data.get("property") or _default_property()
        html = serializer.validated_data.get("html_markup", "")
        css = serializer.validated_data.get("css_stylesheet", "")
        js = serializer.validated_data.get("js_script", "")
        locations = self.request.data.get("locations") or []
        if (html or "").strip():
            self._validate_before_save(html, css, js, locations)
        clean_html = sanitize_template_html(html)
        clean_js = sanitize_template_js(js)
        instance = serializer.save(
            property=prop,
            created_by=self.request.user,
            html_markup=clean_html,
            js_script=clean_js,
        )
        if locations:
            sync_locations_to_zones(instance, locations)
        append_map_revision(instance, note="create")
        instance.save(update_fields=["revision_history_json"])

    @staticmethod
    def _validate_before_save(
        html: str, css: str, js: str, locations: list
    ) -> None:
        agent = MapStudioAgent()
        review = agent.validate_map(
            html_markup=html,
            css_stylesheet=css,
            js_script=js,
            locations=locations,
        )
        if not review.get("valid"):
            raise DRFValidationError(
                review.get("summary") or "; ".join(review.get("issues") or [])
            )


class VenueMapDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = VenueMapSerializer
    permission_classes = [IsDesignerOrAdminRole]

    def get_queryset(self):
        return _map_queryset_for_user(self.request.user).prefetch_related("zones")

    def perform_update(self, serializer):
        html_fields = ("html_markup", "css_stylesheet", "js_script")
        if not any(k in serializer.validated_data for k in html_fields):
            serializer.save()
            return
        html = serializer.validated_data.get("html_markup", serializer.instance.html_markup)
        css = serializer.validated_data.get(
            "css_stylesheet", serializer.instance.css_stylesheet
        )
        js = serializer.validated_data.get("js_script", serializer.instance.js_script)
        locations = self.request.data.get("locations") or []
        VenueMapListCreateView._validate_before_save(html, css, js, locations)
        clean_html = sanitize_template_html(html)
        clean_js = sanitize_template_js(js)
        instance = serializer.save(html_markup=clean_html, js_script=clean_js)
        if locations:
            sync_locations_to_zones(instance, locations)
        append_map_revision(instance, note="update")
        instance.save(update_fields=["revision_history_json"])


class VenueMapDuplicateView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

    def post(self, request, pk):
        source = _map_queryset_for_user(request.user).filter(pk=pk).first()
        if not source:
            return Response(status=status.HTTP_404_NOT_FOUND)
        clone = InteractiveVenueMap.objects.create(
            property=source.property,
            title=f"{source.title} (copy)",
            html_markup=source.html_markup,
            css_stylesheet=source.css_stylesheet,
            js_script=source.js_script,
            chat_history_json=list(source.chat_history_json or []),
            created_by=request.user,
        )
        for zone in source.zones.all():
            VenueMapZone.objects.create(
                venue_map=clone,
                svg_element_id=zone.svg_element_id,
                zone_label=zone.zone_label,
                polygon_coords_json=zone.polygon_coords_json,
                display_metadata_json=dict(zone.display_metadata_json or {}),
                space_inventory=zone.space_inventory,
                updated_by_agent=zone.updated_by_agent,
            )
        return Response(VenueMapSerializer(clone).data, status=status.HTTP_201_CREATED)


class VenueMapRestoreRevisionView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

    def post(self, request, pk):
        venue_map = _map_queryset_for_user(request.user).filter(pk=pk).first()
        if not venue_map:
            return Response(status=status.HTTP_404_NOT_FOUND)
        index = int(request.data.get("index", -1))
        history = list(venue_map.revision_history_json or [])
        if index < 0 or index >= len(history):
            return Response({"detail": "invalid revision index"}, status=400)
        rev = history[index]
        venue_map.title = rev.get("title", venue_map.title)
        venue_map.html_markup = rev.get("html_markup", "")
        venue_map.css_stylesheet = rev.get("css_stylesheet", "")
        venue_map.js_script = rev.get("js_script", "")
        venue_map.save(
            update_fields=[
                "title",
                "html_markup",
                "css_stylesheet",
                "js_script",
                "updated_at",
            ]
        )
        return Response(VenueMapSerializer(venue_map).data)


class VenueMapExportView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

    def get(self, request, pk):
        venue_map = _map_queryset_for_user(request.user).filter(pk=pk).prefetch_related("zones").first()
        if not venue_map:
            return Response(status=status.HTTP_404_NOT_FOUND)
        zones = [zone_detail_bundle(z) for z in venue_map.zones.all()]
        return Response(
            {
                "title": venue_map.title,
                "html_markup": venue_map.html_markup,
                "css_stylesheet": venue_map.css_stylesheet,
                "js_script": venue_map.js_script,
                "compiled_html": compile_interactive_map(
                    venue_map.html_markup,
                    venue_map.css_stylesheet,
                    js_script=venue_map.js_script,
                ),
                "locations": zones,
            }
        )


class DefaultVenueMapView(generics.RetrieveAPIView):
    serializer_class = VenueMapSerializer
    permission_classes = []

    def get_object(self):
        return InteractiveVenueMap.objects.filter(is_default=True).prefetch_related("zones").first()


class PublishedVenueMapView(APIView):
    """Client-facing compiled map + zone details (no auth required for demo)."""

    permission_classes = []

    def get(self, request):
        venue_map = (
            InteractiveVenueMap.objects.filter(is_default=True)
            .prefetch_related("zones")
            .first()
        )
        if not venue_map:
            return Response({"detail": "No default venue map"}, status=404)
        zones = [zone_detail_bundle(z) for z in venue_map.zones.all()]
        return Response(
            {
                "id": str(venue_map.id),
                "title": venue_map.title,
                "compiled_html": compile_interactive_map(
                    venue_map.html_markup,
                    venue_map.css_stylesheet,
                    js_script=venue_map.js_script,
                ),
                "html_markup": venue_map.html_markup,
                "css_stylesheet": venue_map.css_stylesheet,
                "js_script": venue_map.js_script,
                "locations": zones,
            }
        )


class MapMediaUploadView(APIView):
    permission_classes = [IsDesignerOrAdminRole]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "file is required"}, status=status.HTTP_400_BAD_REQUEST)
        venue_map = None
        venue_map_id = request.data.get("venue_map_id")
        if venue_map_id:
            venue_map = _map_queryset_for_user(request.user).filter(pk=venue_map_id).first()
        try:
            asset = save_designer_asset(
                designer=request.user,
                upload=upload,
                request=request,
                venue_map=venue_map,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            DesignerMediaAssetSerializer(asset, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class MapMediaListView(generics.ListAPIView):
    serializer_class = DesignerMediaAssetSerializer
    permission_classes = [IsDesignerOrAdminRole]

    def get_queryset(self):
        qs = DesignerMediaAsset.objects.filter(designer=self.request.user).order_by(
            "-created_at"
        )
        venue_map_id = self.request.query_params.get("venue_map_id")
        if venue_map_id:
            qs = qs.filter(venue_map_id=venue_map_id)
        return qs[:100]


class MapChatView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

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
        venue_map_id = request.data.get("venue_map_id")

        assets = list(
            DesignerMediaAsset.objects.filter(id__in=attachment_ids, designer=request.user)
        )
        attachment_block = format_assets_for_agent(assets)

        agent = MapStudioAgent()
        result = agent.chat_turn(
            message=message or "Build an interactive venue map from the attached floorplan.",
            history=history,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            js_script=js_script,
            attachment_block=attachment_block,
        )

        display_message = message
        if assets:
            names = ", ".join(a.original_name for a in assets)
            display_message = f"{message}\n[Attachments: {names}]".strip()

        new_history = list(history)
        now = timezone.now().isoformat()
        if display_message:
            new_history.append({"role": "user", "content": display_message, "ts": now})
        new_history.append(
            {
                "role": "assistant",
                "content": result["assistant_message"],
                "ts": timezone.now().isoformat(),
            }
        )

        locations = result.get("locations") or []
        if venue_map_id:
            venue_map = _map_queryset_for_user(request.user).filter(pk=venue_map_id).first()
            if venue_map:
                venue_map.chat_history_json = new_history
                venue_map.html_markup = sanitize_template_html(result["html_markup"])
                venue_map.css_stylesheet = result["css_stylesheet"]
                venue_map.js_script = sanitize_template_js(result["js_script"])
                venue_map.save(
                    update_fields=[
                        "chat_history_json",
                        "html_markup",
                        "css_stylesheet",
                        "js_script",
                        "updated_at",
                    ]
                )
                if locations:
                    sync_locations_to_zones(venue_map, locations)

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


class MapValidateView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

    def post(self, request):
        html = request.data.get("html_markup") or ""
        css = request.data.get("css_stylesheet") or ""
        js = request.data.get("js_script") or ""
        locations = request.data.get("locations") or []
        compiled = request.data.get("compiled_html") or compile_interactive_map(html, css, js_script=js)
        agent = MapStudioAgent()
        review = agent.validate_map(
            html_markup=html,
            css_stylesheet=css,
            js_script=js,
            locations=locations,
            compiled_html=compiled,
        )
        return Response(review)


class MapPreviewView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

    def post(self, request):
        html = request.data.get("html_markup") or ""
        css = request.data.get("css_stylesheet") or ""
        js = request.data.get("js_script") or ""
        return Response(
            {"compiled_html": compile_interactive_map(html, css, js_script=js)}
        )


class ZoneDetailBundleView(APIView):
    permission_classes = []

    def get(self, request, pk):
        zone = VenueMapZone.objects.filter(pk=pk).select_related("venue_map").first()
        if not zone:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(zone_detail_bundle(zone))


class VenueMapVectorizeView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

    def post(self, request, pk):
        venue_map = _map_queryset_for_user(request.user).get(pk=pk)
        try:
            vectorize_map(venue_map)
            return Response({"status": "ok", "fallback": False})
        except MapVectorizationFallbackHandler as exc:
            return Response(
                {"status": "fallback", "message": str(exc), "editor_enabled": True},
                status=status.HTTP_202_ACCEPTED,
            )


class VenueMapVerifyView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

    def post(self, request, pk):
        venue_map = _map_queryset_for_user(request.user).get(pk=pk)
        venue_map.is_verified = True
        venue_map.verified_by = request.user
        venue_map.save(update_fields=["is_verified", "verified_by"])
        return Response({"status": "verified"})


class VenueMapZoneUpdateView(generics.UpdateAPIView):
    queryset = VenueMapZone.objects.all()
    serializer_class = VenueMapZoneSerializer
    permission_classes = [IsDesignerOrAdminRole]


class AgentTagZoneView(APIView):
    permission_classes = [IsDesignerOrAdminRole]

    def post(self, request):
        zone = VenueMapZone.objects.get(pk=request.data["zone_id"])
        zone.zone_label = request.data.get("zone_label", zone.zone_label)
        meta = zone.display_metadata_json or {}
        meta.update(request.data.get("metadata", {}))
        zone.display_metadata_json = meta
        if request.data.get("space_inventory_id"):
            zone.space_inventory_id = request.data["space_inventory_id"]
        zone.updated_by_agent = True
        zone.save()
        return Response(VenueMapZoneSerializer(zone).data)
