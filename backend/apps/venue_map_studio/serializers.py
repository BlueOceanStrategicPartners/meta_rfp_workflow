from rest_framework import serializers

from apps.inventory.models import InteractiveVenueMap, VenueMapZone, VenueProperty


class VenueMapZoneSerializer(serializers.ModelSerializer):
    detail = serializers.SerializerMethodField()

    class Meta:
        model = VenueMapZone
        fields = (
            "id",
            "venue_map",
            "svg_element_id",
            "space_inventory",
            "zone_label",
            "polygon_coords_json",
            "display_metadata_json",
            "updated_by_agent",
            "detail",
        )

    def get_detail(self, obj):
        from apps.venue_map_studio.map_services import zone_detail_bundle

        return zone_detail_bundle(obj)


class VenueMapSerializer(serializers.ModelSerializer):
    zones = VenueMapZoneSerializer(many=True, read_only=True)
    property = serializers.PrimaryKeyRelatedField(
        queryset=VenueProperty.objects.all(),
        required=False,
    )

    class Meta:
        model = InteractiveVenueMap
        fields = (
            "id",
            "property",
            "title",
            "source_image_file",
            "generated_html_svg",
            "html_markup",
            "css_stylesheet",
            "js_script",
            "chat_history_json",
            "revision_history_json",
            "is_default",
            "is_verified",
            "version",
            "vectorization_confidence",
            "zones",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("is_verified", "vectorization_confidence", "generated_html_svg")
