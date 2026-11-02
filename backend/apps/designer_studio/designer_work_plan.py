"""User-visible work plans for Design Agent progress (mapped to real pipeline stages)."""
from __future__ import annotations

from typing import Any, Literal

from django.conf import settings

from apps.rfp_debate.meta_client import MetaModelClient

from .designer_map_intent import message_has_map_intent

StepStatus = Literal["pending", "active", "done", "skipped"]

DEFAULT_LABELS: dict[str, str] = {
    "understand_brief": "Review your brief, attachments, and current proposal",
    "draft_proposal": "Update the proposal design and interactions",
    "validate_repair": "Run quality checks and apply fixes",
    "preview_audit": "Review how the live preview looks",
    "finalize": "Wrap up and sync your proposal",
}

PLAN_SYSTEM = (
    "You write short progress labels for a hospitality proposal design assistant. "
    "Return JSON only: {\"labels\": {\"step_id\": \"user-facing sentence\"}}. "
    "Use 6-12 words per label, plain language for sales/event planners — no HTML, CSS, JS, "
    "templates, tools, or developer jargon. Only include keys present in the allowed step list."
)


def _heuristic_labels(message: str, step_ids: list[str]) -> dict[str, str]:
    lower = (message or "").lower()
    out: dict[str, str] = {}
    for step_id in step_ids:
        if step_id == "understand_brief":
            if "attach" in lower or "floorplan" in lower or "image" in lower:
                out[step_id] = "Review your brief and uploaded attachments"
            else:
                out[step_id] = DEFAULT_LABELS[step_id]
        elif step_id == "draft_proposal":
            if "map" in lower or "floorplan" in lower:
                out[step_id] = "Update layout and the venue map area"
            elif "color" in lower or "brand" in lower or "style" in lower:
                out[step_id] = "Apply branding and styling updates"
            else:
                out[step_id] = DEFAULT_LABELS[step_id]
        elif step_id == "validate_repair":
            out[step_id] = DEFAULT_LABELS[step_id]
        elif step_id == "preview_audit":
            out[step_id] = "Check the live preview (layout, map, buttons)"
        elif step_id == "finalize":
            out[step_id] = DEFAULT_LABELS[step_id]
        else:
            out[step_id] = DEFAULT_LABELS.get(step_id, step_id.replace("_", " ").title())
    return out


def personalize_plan_labels(message: str, step_ids: list[str]) -> dict[str, str]:
    base = _heuristic_labels(message, step_ids)
    if not getattr(settings, "DESIGNER_WORK_PLAN_LLM_LABELS", False):
        return base
    if settings.USE_FIXTURE_DEBATE or not getattr(settings, "META_MODEL_API_KEY", ""):
        return base
    client = MetaModelClient()
    allowed = ", ".join(step_ids)
    try:
        raw = client.complete_json_messages(
            model_id=settings.META_MODEL_SPARK,
            messages=[
                {"role": "system", "content": PLAN_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        f"Allowed step ids: {allowed}\n\n"
                        f"Designer request:\n{(message or '')[:2000]}"
                    ),
                },
            ],
            fixture_kind="designer_work_plan",
        )
    except Exception:
        return base
    labels = raw.get("labels") if isinstance(raw, dict) else None
    if not isinstance(labels, dict):
        return base
    merged = dict(base)
    for step_id in step_ids:
        val = labels.get(step_id)
        if isinstance(val, str) and val.strip():
            merged[step_id] = val.strip()[:120]
    return merged


def build_work_plan(
    *,
    message: str,
    include_preview_audit: bool,
    short_path: bool = False,
) -> list[dict[str, Any]]:
    """Return ordered steps with stable ids tied to the designer chat pipeline."""
    if short_path:
        labels = personalize_plan_labels(message, ["understand_brief", "finalize"])
        return [
            {"id": "understand_brief", "label": labels["understand_brief"], "status": "pending"},
            {"id": "finalize", "label": labels["finalize"], "status": "pending"},
        ]

    step_ids = ["understand_brief", "draft_proposal", "validate_repair"]
    if include_preview_audit:
        step_ids.append("preview_audit")
    step_ids.append("finalize")

    labels = personalize_plan_labels(message, step_ids)
    return [
        {"id": step_id, "label": labels.get(step_id, DEFAULT_LABELS.get(step_id, step_id)), "status": "pending"}
        for step_id in step_ids
    ]


def guess_include_venue_map(message: str, has_image_attachment: bool) -> bool:
    """Deprecated — map is edited inside proposal html; kept for tests importing the name."""
    return message_has_map_intent(message) and has_image_attachment


class WorkPlanTracker:
    """Mutable plan state for SSE step events."""

    def __init__(self, steps: list[dict[str, Any]]):
        self._steps = [dict(s) for s in steps]

    def snapshot(self) -> list[dict[str, Any]]:
        return [dict(s) for s in self._steps]

    def _index(self, step_id: str) -> int:
        for i, step in enumerate(self._steps):
            if step.get("id") == step_id:
                return i
        return -1

    def set_status(self, step_id: str, status: StepStatus) -> list[dict[str, Any]]:
        idx = self._index(step_id)
        if idx < 0:
            return self.snapshot()
        if status == "active":
            for i, step in enumerate(self._steps):
                if step.get("status") == "active" and i != idx:
                    step["status"] = "pending"
        self._steps[idx]["status"] = status
        return self.snapshot()
