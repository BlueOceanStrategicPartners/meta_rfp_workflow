from rest_framework import serializers

from .models import ProposalTemplate


class ProposalTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalTemplate
        fields = (
            "id",
            "name",
            "html_markup",
            "css_stylesheet",
            "required_placeholders_json",
            "is_default",
            "updated_at",
        )
        read_only_fields = ("required_placeholders_json",)
