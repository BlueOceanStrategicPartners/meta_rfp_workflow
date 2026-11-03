import uuid

from django.conf import settings
from django.db import models


class AdminAuditEvent(models.Model):
    """Who changed what in the Admin Command Center (and system events such as takeovers)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="admin_audit_events",
    )
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=32)
    target_id = models.CharField(max_length=64, db_index=True)
    payload_json = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.action} {self.target_type}:{self.target_id}"
