import uuid

from django.conf import settings
from django.db import models, transaction


REQUIRED_PLACEHOLDERS = [
    "{{client_name}}",
    "{{event_dates}}",
    "{{verified_room_blocks}}",
    "{{selected_map_svg}}",
    "{{meeting_space_specs}}",
    "{{xgboost_quote_breakdown}}",
    "{{negotiated_concessions}}",
    "{{cta_accept_button}}",
]


class ProposalTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    designer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="proposal_templates",
    )
    html_markup = models.TextField()
    css_stylesheet = models.TextField(blank=True)
    js_script = models.TextField(blank=True)
    required_placeholders_json = models.JSONField(default=list)
    is_default = models.BooleanField(default=False)
    chat_history_json = models.JSONField(default=list)
    revision_history_json = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.is_default:
                ProposalTemplate.objects.filter(is_default=True).exclude(pk=self.pk).update(
                    is_default=False
                )
            super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class MediaAssetType(models.TextChoices):
    IMAGE = "IMAGE", "Image"
    VIDEO = "VIDEO", "Video"


class DesignerMediaAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    designer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="designer_media_assets",
    )
    template = models.ForeignKey(
        ProposalTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_assets",
    )
    venue_map = models.ForeignKey(
        "inventory.InteractiveVenueMap",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="media_assets",
    )
    file = models.FileField(upload_to="designer_assets/%Y/%m/")
    original_name = models.CharField(max_length=512)
    content_type = models.CharField(max_length=128, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    media_type = models.CharField(max_length=16, choices=MediaAssetType.choices)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    metadata_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.original_name
