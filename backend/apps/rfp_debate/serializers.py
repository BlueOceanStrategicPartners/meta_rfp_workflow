from rest_framework import serializers

from .models import RFPSubmission


class RFPSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = RFPSubmission
        fields = (
            "id",
            "status",
            "verified_extraction_json",
            "active_ui_cards_json",
            "selected_map_zones_json",
            "amber_conflict_fields_json",
            "sla_started_at",
            "sla_completed_at",
            "source_document_text",
            "created_at",
        )
        read_only_fields = (
            "id",
            "status",
            "verified_extraction_json",
            "active_ui_cards_json",
        )
