"""Designer chat: proposal layout + optional interactive map stage (replaces separate Map Studio flow)."""
from __future__ import annotations

from typing import Any

from apps.designer_studio.map_interaction_normalize import normalize_map_interaction
from apps.designer_studio.models import ProposalTemplate
from apps.guardrails.validators import sanitize_template_html, sanitize_template_js
from apps.inventory.models import InteractiveVenueMap, VenueProperty
from apps.venue_map_studio.map_markup_guard import normalize_map_record_markup
from apps.venue_map_studio.map_agent import MapStudioAgent
from apps.venue_map_studio.map_services import sync_locations_to_zones

from .designer_chat_guards import user_message_expects_floorplan_upload

SKIP_PHRASES = (
    "skip",
    "no questions",
    "don't ask",
    "do not ask",
    "just create",
    "just build",
    "without questions",
    "no follow",
)

MAP_KEYWORDS = (
    "map",
    "floorplan",
    "floor plan",
    "venue layout",
    "interactive map",
    "ballroom",
    "floorplate",
)


def user_wants_direct_create(message: str) -> bool:
    lower = (message or "").lower()
    return any(p in lower for p in SKIP_PHRASES)


def message_has_map_intent(message: str) -> bool:
    lower = (message or "").lower()
    return any(k in lower for k in MAP_KEYWORDS)


def should_run_map_stage(
    *,
    message: str,
    design_result: dict[str, Any],
    has_image_attachment: bool,
    skip_questions: bool,
) -> bool:
    """Run Map Studio agent after proposal pass when we have enough to build or user opted out of Q&A."""
    html = design_result.get("html_markup") or ""
    has_slot = "{{selected_map_svg}}" in html
    clarifications = design_result.get("clarification_options") or []
    assistant = (design_result.get("assistant_message") or "").lower()

    if not has_slot and not message_has_map_intent(message):
        return False

    if has_image_attachment and (message_has_map_intent(message) or has_slot):
        return True

    if skip_questions and (message_has_map_intent(message) or has_slot):
        return True

    if skip_questions and "proposal" in message.lower() and has_slot:
        return True

    # Designer asked for floorplan; user sent only attachments this turn
    if has_image_attachment and not clarifications and (
        "floorplan" in assistant or "floor plan" in assistant or "upload" in assistant
    ):
        return True

    if message_has_map_intent(message) and skip_questions:
        return True

    return False


def build_map_agent_message(
    *,
    user_message: str,
    design_assistant: str,
    skip_questions: bool,
    has_image_attachment: bool,
) -> str:
    parts = [
        "Build or update the interactive venue map for this proposal template.",
        f"Designer context: {design_assistant[:1200]}",
        f"User request: {user_message.strip()}",
    ]
    if skip_questions:
        parts.append(
            "User asked to skip follow-up questions — use sensible default zone labels "
            "and capacities from the proposal context; do not ask more questions."
        )
    if has_image_attachment:
        parts.append("Use the attached floorplan image URL(s) as the map background/reference.")
    elif skip_questions:
        parts.append(
            "No floorplan image was provided — produce a clean schematic interactive map "
            "with labeled clickable zones anyway."
        )
    return "\n".join(parts)


def resolve_template_venue_map(
    *,
    template: ProposalTemplate | None,
    user,
) -> InteractiveVenueMap | None:
    if template is None:
        prop = VenueProperty.objects.order_by("id").first()
        if not prop:
            prop, _ = VenueProperty.objects.get_or_create(name="Default Property")
        existing = (
            InteractiveVenueMap.objects.filter(created_by=user, is_default=True)
            .order_by("-updated_at")
            .first()
        )
        if existing:
            return existing
        return InteractiveVenueMap.objects.create(
            property=prop,
            title="Designer venue map",
            created_by=user,
        )

    prefix = f"Template: {template.name}"[:250]
    venue_map = (
        InteractiveVenueMap.objects.filter(created_by=user, title=prefix)
        .order_by("-updated_at")
        .first()
    )
    if venue_map:
        return venue_map
    prop = VenueProperty.objects.order_by("id").first()
    if not prop:
        prop, _ = VenueProperty.objects.get_or_create(name="Default Property")
    return InteractiveVenueMap.objects.create(
        property=prop,
        title=prefix,
        created_by=user,
    )


def apply_map_stage(
    *,
    venue_map: InteractiveVenueMap,
    map_result: dict[str, Any],
) -> InteractiveVenueMap:
    raw_html = sanitize_template_html(map_result.get("html_markup") or "")
    cleaned_html, _warnings = normalize_map_record_markup(raw_html)
    venue_map.html_markup = cleaned_html
    venue_map.css_stylesheet = map_result.get("css_stylesheet") or ""
    venue_map.js_script = sanitize_template_js(map_result.get("js_script") or "")
    venue_map.html_markup, venue_map.css_stylesheet, venue_map.js_script = normalize_map_interaction(
        venue_map.html_markup,
        venue_map.css_stylesheet,
        venue_map.js_script,
    )
    locations = map_result.get("locations") or []
    if locations:
        sync_locations_to_zones(venue_map, locations)
    venue_map.is_default = True
    InteractiveVenueMap.objects.filter(is_default=True).exclude(pk=venue_map.pk).update(
        is_default=False
    )
    venue_map.save(
        update_fields=[
            "html_markup",
            "css_stylesheet",
            "js_script",
            "is_default",
            "updated_at",
        ]
    )
    return venue_map


def merge_clarification_options(
    design_result: dict[str, Any],
    map_result: dict[str, Any] | None,
    *,
    map_ran: bool,
) -> list[str]:
    if map_ran and map_result:
        opts = map_result.get("clarification_options") or []
        if opts:
            return [str(o) for o in opts if o][:6]
        return []
    opts = design_result.get("clarification_options") or []
    return [str(o) for o in opts if o][:6]


def run_map_stage_if_needed(
    *,
    message: str,
    design_result: dict[str, Any],
    assets: list,
    attachment_block: str,
    template: ProposalTemplate | None,
    user,
) -> tuple[dict[str, Any] | None, InteractiveVenueMap | None]:
    has_image = any(getattr(a, "media_type", None) == "IMAGE" for a in assets)
    skip = user_wants_direct_create(message)

    if user_message_expects_floorplan_upload(message) and not has_image and not skip:
        return None, None

    if not should_run_map_stage(
        message=message,
        design_result=design_result,
        has_image_attachment=has_image,
        skip_questions=skip,
    ):
        return None, None

    venue_map = resolve_template_venue_map(template=template, user=user)
    map_agent = MapStudioAgent()
    map_message = build_map_agent_message(
        user_message=message,
        design_assistant=design_result.get("assistant_message") or "",
        skip_questions=skip,
        has_image_attachment=has_image,
    )
    map_result = map_agent.chat_turn(
        message=map_message,
        history=[],
        html_markup=venue_map.html_markup or "",
        css_stylesheet=venue_map.css_stylesheet or "",
        js_script=venue_map.js_script or "",
        attachment_block=attachment_block,
    )
    apply_map_stage(venue_map=venue_map, map_result=map_result)
    return map_result, venue_map
