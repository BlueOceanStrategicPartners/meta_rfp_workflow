from __future__ import annotations

from typing import Any

from .models import AdminAuditEvent


def record(actor, action: str, target_type: str, target_id, **payload: Any) -> AdminAuditEvent:
    """Write one audit row. `actor` may be None for system events."""
    user = actor if getattr(actor, "is_authenticated", False) else None
    return AdminAuditEvent.objects.create(
        actor=user,
        action=action,
        target_type=target_type,
        target_id=str(target_id),
        payload_json=payload,
    )


def serialize_event(event: AdminAuditEvent) -> dict:
    return {
        "id": str(event.id),
        "action": event.action,
        "actor": event.actor.email if event.actor_id else None,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "payload": event.payload_json,
        "created_at": event.created_at.isoformat(),
    }
