"""Designer chat + API helpers: list, delete, set default, remove map from proposal."""
from __future__ import annotations

import re
import uuid
from typing import Any

from django.db import transaction

from apps.inventory.models import InteractiveVenueMap

from .venue_map_context import remove_map_slot_from_template

# Imperative map-library commands only — never match long proposal-design briefs.
_ADMIN_LIST_RE = re.compile(
    r"^(?:list|show)\s+(?:my\s+)?(?:saved\s+)?(?:venue\s+)?maps?\b",
    re.IGNORECASE,
)
_ADMIN_MAP_LIBRARY_RE = re.compile(
    r"^(?:map\s+(?:history|histories|library)|(?:saved|which)\s+(?:venue\s+)?maps?)\b",
    re.IGNORECASE,
)
_ADMIN_SET_DEFAULT_RE = re.compile(
    r"(?:^|\n)\s*(?:make|set|switch|change)\s+.+\s+(?:as\s+)?(?:the\s+)?default\s+(?:venue\s+)?map\s*$"
    r"|^(?:make|set|switch)\s+.+\s+as\s+default\s+(?:venue\s+)?map?\s*$",
    re.IGNORECASE | re.DOTALL,
)
_ADMIN_DELETE_RE = re.compile(
    r"^(?:delete|remove)\s+(?:the\s+)?(?:venue\s+)?map(?:\s+|$)",
    re.IGNORECASE,
)
_ADMIN_PROPOSAL_REMOVE_RE = re.compile(
    r"^remove\s+(?:the\s+)?(?:venue\s+)?map\s+(?:section\s+)?from\s+(?:this\s+)?proposal",
    re.IGNORECASE,
)

_DESIGN_BRIEF_SIGNALS = (
    "proposal",
    "interactive",
    "animation",
    "transition",
    "background",
    "create",
    "design",
    "layout",
    "theme",
    "hero",
    "element",
    "branding",
    "gallery",
    "rfp",
    "icons",
    "typography",
    "css",
    "html",
)


def _maps_for_user(user):
    qs = InteractiveVenueMap.objects.all().order_by("-updated_at")
    if getattr(user, "role", None) == "ADMIN":
        return qs
    return qs.filter(created_by=user)


def _is_proposal_design_message(message: str) -> bool:
    """True when the user is clearly asking for proposal/layout work, not library admin."""
    text = (message or "").strip()
    if len(text) > 140:
        return True
    lower = text.lower()
    signals = sum(1 for s in _DESIGN_BRIEF_SIGNALS if s in lower)
    if signals >= 2:
        return True
    if signals >= 1 and len(text) > 70:
        return True
    return False


def _resolve_map(user, message: str) -> InteractiveVenueMap | None:
    lower = (message or "").lower()
    maps = list(_maps_for_user(user))
    if not maps:
        return None

    for token in re.findall(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        message or "",
        flags=re.IGNORECASE,
    ):
        try:
            uid = uuid.UUID(token)
        except ValueError:
            continue
        match = next((m for m in maps if m.pk == uid), None)
        if match:
            return match

    best: InteractiveVenueMap | None = None
    best_len = 0
    for m in maps:
        title = (m.title or "").lower()
        if len(title) >= 3 and title in lower:
            if len(title) > best_len:
                best = m
                best_len = len(title)
    if best:
        return best

    if re.search(r"\b(?:the\s+)?default\s+(?:venue\s+)?map\b", lower) and not _is_proposal_design_message(
        message
    ):
        default = next((m for m in maps if m.is_default), None)
        if default:
            return default

    if len(maps) == 1 and len(message.strip()) < 100:
        return maps[0]
    return None


def _intent(message: str) -> str | None:
    text = (message or "").strip()
    if not text:
        return None

    if _is_proposal_design_message(text):
        return None

    if _ADMIN_PROPOSAL_REMOVE_RE.search(text) or "remove map slot" in text.lower():
        return "proposal_remove"

    lower = text.lower()
    if _ADMIN_LIST_RE.match(text) or _ADMIN_MAP_LIBRARY_RE.match(text):
        return "list"

    if _ADMIN_SET_DEFAULT_RE.match(text.strip()):
        return "set_default"

    if _ADMIN_DELETE_RE.match(text):
        return "delete"

    return None


def set_default_map(user, venue_map: InteractiveVenueMap) -> InteractiveVenueMap:
    venue_map.is_default = True
    venue_map.save(update_fields=["is_default", "updated_at"])
    return venue_map


def delete_map(user, venue_map: InteractiveVenueMap) -> str | None:
    """Delete map; promote another to default if needed. Returns error message or None."""
    qs = _maps_for_user(user)
    if not qs.filter(pk=venue_map.pk).exists():
        return "Map not found."
    was_default = venue_map.is_default
    with transaction.atomic():
        venue_map.delete()
        if was_default:
            nxt = qs.exclude(pk=venue_map.pk).order_by("-updated_at").first()
            if nxt:
                nxt.is_default = True
                nxt.save(update_fields=["is_default", "updated_at"])
    return None


def serialize_map_summary(venue_map: InteractiveVenueMap) -> dict[str, Any]:
    revs = venue_map.revision_history_json or []
    return {
        "id": str(venue_map.id),
        "title": venue_map.title,
        "is_default": venue_map.is_default,
        "updated_at": venue_map.updated_at.isoformat(),
        "revision_count": len(revs),
    }


def list_maps_payload(user) -> list[dict[str, Any]]:
    return [serialize_map_summary(m) for m in _maps_for_user(user)]


def try_handle_venue_map_admin_message(
    *,
    message: str,
    user,
    html_markup: str,
    css_stylesheet: str,
) -> dict[str, Any] | None:
    intent = _intent(message)
    if not intent:
        return None

    maps = list(_maps_for_user(user))

    if intent == "list":
        items = list_maps_payload(user)
        if not items:
            text = (
                "You have no saved venue maps yet. Ask me to build an interactive map "
                "or upload a floorplan in chat."
            )
        else:
            lines = [
                f"- {m['title']}{' (default)' if m['is_default'] else ''} — "
                f"{m['revision_count']} revision(s), updated {m['updated_at'][:10]}"
                for m in items
            ]
            text = "Saved venue maps:\n" + "\n".join(lines)
        return _admin_response(
            assistant_message=text,
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            venue_maps=items,
            action="list",
        )

    if intent == "proposal_remove":
        new_html = remove_map_slot_from_template(html_markup)
        if new_html == (html_markup or ""):
            text = "This proposal has no venue map section to remove."
        else:
            text = (
                "Removed the venue map section from this proposal template. "
                "Saved maps in your library are unchanged — open Venue maps in the Live preview toolbar to manage them."
            )
        return _admin_response(
            assistant_message=text,
            html_markup=new_html,
            css_stylesheet=css_stylesheet,
            venue_maps=list_maps_payload(user),
            action="proposal_remove",
            template_updated=new_html != (html_markup or ""),
        )

    target = _resolve_map(user, message)
    if not target and intent in {"delete", "set_default"}:
        if not maps:
            return _admin_response(
                assistant_message=(
                    "There are no saved venue maps yet. "
                    "Describe the proposal you want — I'll add a map slot and can build the interactive map next."
                ),
                html_markup=html_markup,
                css_stylesheet=css_stylesheet,
                venue_maps=[],
                action=intent,
            )
        titles = ", ".join(f"“{m.title}”" for m in maps[:6])
        return _admin_response(
            assistant_message=(
                f"I need which map you mean. Saved maps: {titles}. "
                "Say “make [title] the default map” or “delete map [title]”."
            ),
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            venue_maps=list_maps_payload(user),
            action=intent,
        )

    if intent == "set_default" and target:
        set_default_map(user, target)
        return _admin_response(
            assistant_message=f"{target.title} is now the default venue map for proposals and live preview.",
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            venue_maps=list_maps_payload(user),
            action="set_default",
            venue_map_id=str(target.id),
            venue_map_title=target.title,
        )

    if intent == "delete" and target:
        err = delete_map(user, target)
        if err:
            return _admin_response(
                assistant_message=err,
                html_markup=html_markup,
                css_stylesheet=css_stylesheet,
                venue_maps=list_maps_payload(user),
                action="delete",
            )
        return _admin_response(
            assistant_message=f"Deleted venue map “{target.title}”. "
            "Open Venue maps in the Live preview toolbar to choose another default if needed.",
            html_markup=html_markup,
            css_stylesheet=css_stylesheet,
            venue_maps=list_maps_payload(user),
            action="delete",
        )

    return None


def _admin_response(
    *,
    assistant_message: str,
    html_markup: str,
    css_stylesheet: str,
    venue_maps: list[dict[str, Any]],
    action: str,
    venue_map_id: str | None = None,
    venue_map_title: str | None = None,
    template_updated: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "assistant_message": assistant_message,
        "html_markup": html_markup,
        "css_stylesheet": css_stylesheet,
        "js_script": "",
        "clarification_options": [],
        "venue_maps_action": action,
        "venue_maps": venue_maps,
        "map_stage_applied": False,
        "self_check": {"valid": True, "issues": []},
    }
    if venue_map_id:
        payload["venue_map_id"] = venue_map_id
    if venue_map_title:
        payload["venue_map_title"] = venue_map_title
    if template_updated:
        payload["template_updated"] = True
    return payload
