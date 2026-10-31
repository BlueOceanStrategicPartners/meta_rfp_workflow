import uuid

from django.conf import settings
from django.db import models


class RFPStatus(models.TextChoices):
    EXTRACTING = "EXTRACTING", "Extracting"
    DEBATING = "DEBATING", "Debating"
    AWAITING_USER_CARD_EDIT = "AWAITING_USER_CARD_EDIT", "Awaiting user card edit"
    PRICING = "PRICING", "Pricing"
    NEGOTIATING = "NEGOTIATING", "Negotiating"
    PROPOSAL_RENDERED = "PROPOSAL_RENDERED", "Proposal rendered"
    BOOKED = "BOOKED", "Booked"
    ESCALATED = "ESCALATED", "Escalated"


class RFPSubmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rfp_submissions",
    )
    status = models.CharField(
        max_length=32, choices=RFPStatus.choices, default=RFPStatus.EXTRACTING
    )
    verified_extraction_json = models.JSONField(default=dict)
    active_ui_cards_json = models.JSONField(default=dict)
    selected_map_zones_json = models.JSONField(default=list)
    amber_conflict_fields_json = models.JSONField(default=list)
    sla_started_at = models.DateTimeField(null=True, blank=True)
    sla_completed_at = models.DateTimeField(null=True, blank=True)
    source_document_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"RFP {self.id} ({self.status})"


class DebateIterationLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rfp = models.ForeignKey(
        RFPSubmission, on_delete=models.CASCADE, related_name="debate_logs"
    )
    iteration_number = models.PositiveSmallIntegerField()
    extractor_model_id = models.CharField(max_length=128)
    extractor_output_json = models.JSONField(default=dict)
    critic_model_id = models.CharField(max_length=128)
    discrepancy_flags_json = models.JSONField(default=list)
    arbiter_consensus_score = models.FloatField(default=0.0)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["iteration_number"]
        unique_together = ("rfp", "iteration_number")
