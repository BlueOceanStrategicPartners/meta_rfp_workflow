from rest_framework import serializers

from .models import DesignerMediaAsset, ProposalTemplate


class ProposalTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProposalTemplate
        fields = (
            "id",
            "name",
            "html_markup",
            "css_stylesheet",
            "js_script",
            "required_placeholders_json",
            "is_default",
            "chat_history_json",
            "revision_history_json",
            "updated_at",
            "created_at",
        )
        read_only_fields = ("required_placeholders_json", "created_at")


class DesignerMediaAssetSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = DesignerMediaAsset
        fields = (
            "id",
            "url",
            "original_name",
            "content_type",
            "file_size",
            "media_type",
            "width",
            "height",
            "metadata_json",
            "created_at",
        )
        read_only_fields = fields

    def get_url(self, obj: DesignerMediaAsset) -> str:
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(obj.file.url)
        return obj.file.url
