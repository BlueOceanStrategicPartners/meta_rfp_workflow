from rest_framework import serializers

from apps.inventory.models import InteractiveVenueMap, VenueMapZone


class VenueMapSerializer(serializers.ModelSerializer):
    class Meta:
        model = InteractiveVenueMap
        fields = (
            "id",
            "property",
            "title",
            "source_image_file",
            "generated_html_svg",
            "is_verified",
            "version",
            "vectorization_confidence",
        )


class VenueMapZoneSerializer(serializers.ModelSerializer):
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
        )
