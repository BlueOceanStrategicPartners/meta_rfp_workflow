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
    required_placeholders_json = models.JSONField(default=list)
    is_default = models.BooleanField(default=False)
    chat_history_json = models.JSONField(default=list)
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
