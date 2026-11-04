from rest_framework import serializers

from .models import RFPSubmission


class RFPSubmissionSerializer(serializers.ModelSerializer):
    completed = serializers.SerializerMethodField()
    client_session = serializers.SerializerMethodField()

    class Meta:
        model = RFPSubmission
        fields = (
            "id",
            "status",
            "completed",
            "client_session",
            "verified_extraction_json",
            "active_ui_cards_json",
            "selected_map_zones_json",
            "amber_conflict_fields_json",
            "sla_started_at",
            "sla_completed_at",
            "source_document_text",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "status",
            "verified_extraction_json",
            "active_ui_cards_json",
        )

    def get_completed(self, obj: RFPSubmission) -> bool:
        from .client_session_list import COMPLETED_STATUSES

        return obj.status in COMPLETED_STATUSES

    def get_client_session(self, obj: RFPSubmission) -> dict:
        from apps.negotiation_agent.client_session_memory import normalize_session

        return normalize_session(obj.client_session_json)
